/* SPDX-License-Identifier: Apache-2.0 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <inttypes.h>
#include "sdkconfig.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_random.h"
#include "esp_mac.h"
#include "bootloader_random.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "mbedtls/sha256.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#if CONFIG_FS_WIFI
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#endif
#if CONFIG_FS_BLE
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
#include "os/os_mbuf.h"
#endif
static SemaphoreHandle_t lock;
static nvs_handle_t prefs;
static uint8_t token[16];
static uint32_t random_passkey;
static char token_hex[33];
static char ap_password[25];
static char device_name[25];
/* Per-device credentials; kept in a single NVS blob, never shared between builds. */
typedef struct { uint8_t token[16]; uint8_t password[12]; uint32_t passkey; } credentials_t;
static bool busy, committed;
static unsigned owner;
static size_t total, received;
static esp_ota_handle_t handle;
static const esp_partition_t *dest;
static mbedtls_sha256_context hash;
static int64_t touched;
static uint8_t previous=255;
static bool equal(const uint8_t *a,const uint8_t *b,size_t n){uint8_t d=0;while(n--)d|=*a++^*b++;return d==0;}
static int nibble(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static bool unhex(const char *s,uint8_t *out,size_t n){if(strlen(s)!=2*n)return false;for(size_t i=0;i<n;i++){int a=nibble(s[2*i]),b=nibble(s[2*i+1]);if(a<0||b<0)return false;out[i]=(a<<4)|b;}return true;}
static const esp_partition_t *slot(uint8_t n){return esp_partition_find_first(ESP_PARTITION_TYPE_APP, n?ESP_PARTITION_SUBTYPE_APP_OTA_1:ESP_PARTITION_SUBTYPE_APP_OTA_0,NULL);}
static void abort_update(void){if(busy){esp_ota_abort(handle);mbedtls_sha256_free(&hash);}busy=false;owner=0;received=0;}
static bool begin_update(unsigned who,size_t size){
 if(busy||committed||!size)return false;
 dest=slot(previous==0?1:0);if(!dest||size>dest->size)return false;
 if(esp_ota_begin(dest,size,&handle)!=ESP_OK)return false;
 mbedtls_sha256_init(&hash);if(mbedtls_sha256_starts(&hash,0)!=0){esp_ota_abort(handle);mbedtls_sha256_free(&hash);return false;}
 busy=true;owner=who;total=size;received=0;touched=esp_timer_get_time();return true;
}
static bool write_update(unsigned who,size_t offset,const uint8_t *data,size_t len){
 if(!busy||owner!=who||offset!=received||!len||len>total-received)return false;
 if(esp_ota_write(handle,data,len)!=ESP_OK||mbedtls_sha256_update(&hash,data,len)!=0){abort_update();return false;}
 received+=len;touched=esp_timer_get_time();return true;
}
static bool finish_update(unsigned who,const uint8_t expected[32]){
 if(!busy||owner!=who||received!=total)return false;
 uint8_t digest[32];if(mbedtls_sha256_finish(&hash,digest)!=0||!equal(digest,expected,32)){abort_update();return false;}
 mbedtls_sha256_free(&hash);busy=false;owner=0;
 if(esp_ota_end(handle)!=ESP_OK)return false;
 uint8_t next=dest->subtype==ESP_PARTITION_SUBTYPE_APP_OTA_0?0:1;
 /* Store recovery pointer first; if boot selection fails, recovery can retry or reinstall. */
 if(nvs_set_u8(prefs,"previous",next)!=ESP_OK||nvs_commit(prefs)!=ESP_OK)return false;
 previous=next;
 if(esp_ota_set_boot_partition(dest)!=ESP_OK)return false;
 committed=true;return true;
}
static void reboot_task(void *arg){vTaskDelay(pdMS_TO_TICKS(1500));esp_restart();}
static void schedule_reboot(void){if(xTaskCreate(reboot_task,"reboot",2048,NULL,5,NULL)!=pdPASS)esp_restart();}
static bool resume_previous(void){if(busy||committed||previous>1)return false;const esp_partition_t *p=slot(previous);if(!p||esp_ota_set_boot_partition(p)!=ESP_OK)return false;committed=true;return true;}
static void watchdog_task(void *arg){for(;;){vTaskDelay(pdMS_TO_TICKS(1000));xSemaphoreTake(lock,portMAX_DELAY);if(busy&&esp_timer_get_time()-touched>60000000LL)abort_update();xSemaphoreGive(lock);}}
#if CONFIG_FS_WIFI
static bool http_auth(httpd_req_t *r){char buf[40];uint8_t raw[16];return httpd_req_get_hdr_value_str(r,"X-FS-Token",buf,sizeof buf)==ESP_OK&&unhex(buf,raw,16)&&equal(raw,token,16);}
/* Fixed trusted PWA origin. Never reflect arbitrary Origin or allow cookies. */
#define FS_ORIGIN "https://flasher-studio-byvovk.web.app"
static bool http_cors(httpd_req_t *r){
 size_t n=httpd_req_get_hdr_value_len(r,"Origin");if(n==0)return true;
 char origin[80];if(n>=sizeof origin||httpd_req_get_hdr_value_str(r,"Origin",origin,sizeof origin)!=ESP_OK||strcmp(origin,FS_ORIGIN)){httpd_resp_send_err(r,HTTPD_403_FORBIDDEN,"origin rejected");return false;}
 httpd_resp_set_hdr(r,"Access-Control-Allow-Origin",FS_ORIGIN);httpd_resp_set_hdr(r,"Vary","Origin");httpd_resp_set_hdr(r,"Cache-Control","no-store");return true;
}
static esp_err_t http_options(httpd_req_t *r){if(!http_cors(r))return ESP_OK;httpd_resp_set_hdr(r,"Access-Control-Allow-Methods","GET, POST, OPTIONS");httpd_resp_set_hdr(r,"Access-Control-Allow-Headers","X-FS-Token, X-FS-SHA256, Content-Type");httpd_resp_set_hdr(r,"Access-Control-Allow-Private-Network","true");return httpd_resp_send(r,NULL,0);}
static esp_err_t http_info(httpd_req_t *r){
 if(!http_cors(r))return ESP_OK;
 /* Native clients from v0.2.0 still receive public info; web clients must authenticate before identity/layout are disclosed. */
 if(httpd_req_get_hdr_value_len(r,"Origin")&&!http_auth(r))return httpd_resp_send_err(r,HTTPD_403_FORBIDDEN,"authentication required");
 char buf[360];const esp_partition_t *a=slot(0),*b=slot(1);xSemaphoreTake(lock,portMAX_DELAY);
 snprintf(buf,sizeof buf,"{\"protocol\":1,\"version\":\"0.2.1\",\"target\":\"%s\",\"maxBytes\":%lu,\"busy\":%s,\"committed\":%s,\"previous\":%u,\"device\":\"%s\",\"aOffset\":%lu,\"bOffset\":%lu,\"bSize\":%lu}",CONFIG_IDF_TARGET,(unsigned long)(a?a->size:0),busy?"true":"false",committed?"true":"false",previous,device_name,(unsigned long)(a?a->address:0),(unsigned long)(b?b->address:0),(unsigned long)(b?b->size:0));
 xSemaphoreGive(lock);httpd_resp_set_type(r,"application/json");return httpd_resp_sendstr(r,buf);
}
static esp_err_t http_upload(httpd_req_t *r){if(!http_cors(r))return ESP_OK;char hex[65];uint8_t expected[32];if(!http_auth(r))return httpd_resp_send_err(r,HTTPD_403_FORBIDDEN,"authentication required");if(httpd_req_get_hdr_value_str(r,"X-FS-SHA256",hex,sizeof hex)!=ESP_OK||!unhex(hex,expected,32))return httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"SHA256 required");
 xSemaphoreTake(lock,portMAX_DELAY);bool ok=begin_update(1,r->content_len);xSemaphoreGive(lock);if(!ok)return httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"busy or size invalid");
 uint8_t buf[1024];size_t pos=0;while(pos<r->content_len){size_t want=r->content_len-pos;if(want>sizeof buf)want=sizeof buf;int n=httpd_req_recv(r,(char*)buf,want);if(n<=0){ok=false;break;}xSemaphoreTake(lock,portMAX_DELAY);ok=write_update(1,pos,buf,n);xSemaphoreGive(lock);if(!ok)break;pos+=n;}
 xSemaphoreTake(lock,portMAX_DELAY);if(ok)ok=finish_update(1,expected);if(!ok&&busy&&owner==1)abort_update();xSemaphoreGive(lock);if(!ok)return httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"image rejected");esp_err_t res=httpd_resp_sendstr(r,"OK; restarting");schedule_reboot();return res;}
static esp_err_t http_resume(httpd_req_t *r){if(!http_cors(r))return ESP_OK;if(!http_auth(r))return httpd_resp_send_err(r,HTTPD_403_FORBIDDEN,"authentication required");xSemaphoreTake(lock,portMAX_DELAY);bool ok=resume_previous();xSemaphoreGive(lock);if(!ok)return httpd_resp_send_err(r,HTTPD_400_BAD_REQUEST,"no previous image");esp_err_t res=httpd_resp_sendstr(r,"OK; restarting");schedule_reboot();return res;}
static void start_wifi(void){ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());esp_netif_create_default_wifi_ap();wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&init));ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));wifi_config_t cfg={0};snprintf((char*)cfg.ap.ssid,sizeof cfg.ap.ssid,"%s",device_name);snprintf((char*)cfg.ap.password,sizeof cfg.ap.password,"%s",ap_password);cfg.ap.channel=1;cfg.ap.max_connection=1;cfg.ap.authmode=WIFI_AUTH_WPA2_PSK;ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP,&cfg));ESP_ERROR_CHECK(esp_wifi_start());printf("Wi-Fi SSID=%s password=%s URL=http://192.168.4.1\n",cfg.ap.ssid,cfg.ap.password);httpd_handle_t server=NULL;httpd_config_t hc=HTTPD_DEFAULT_CONFIG();hc.recv_wait_timeout=10;hc.stack_size=8192;ESP_ERROR_CHECK(httpd_start(&server,&hc));httpd_uri_t info={.uri="/v1/info",.method=HTTP_GET,.handler=http_info},upload={.uri="/v1/update",.method=HTTP_POST,.handler=http_upload},resume={.uri="/v1/resume",.method=HTTP_POST,.handler=http_resume};ESP_ERROR_CHECK(httpd_register_uri_handler(server,&info));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&upload));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&resume));httpd_uri_t oi={.uri="/v1/info",.method=HTTP_OPTIONS,.handler=http_options},ou={.uri="/v1/update",.method=HTTP_OPTIONS,.handler=http_options},orr={.uri="/v1/resume",.method=HTTP_OPTIONS,.handler=http_options};ESP_ERROR_CHECK(httpd_register_uri_handler(server,&oi));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&ou));ESP_ERROR_CHECK(httpd_register_uri_handler(server,&orr));}
#endif
#if CONFIG_FS_BLE
/* UUIDs (canonical) 6d960001/2/3-b5a3-4b80-a6d8-983a7ad72f11. */
#define FS_UUID(n) BLE_UUID128_INIT(0x11,0x2f,0xd7,0x7a,0x3a,0x98,0xd8,0xa6,0x80,0x4b,0xa3,0xb5,n,0x00,0x96,0x6d)
static ble_uuid128_t service_uuid=FS_UUID(1),cmd_uuid=FS_UUID(2),status_uuid=FS_UUID(3);
static uint8_t addr_type;static uint32_t passkey;static bool authorized;static uint8_t expected_ble[32];static uint8_t digest_parts;
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int ble_access(uint16_t conn,uint16_t attr,struct ble_gatt_access_ctxt *ctxt,void *arg){
 if(ctxt->op==BLE_GATT_ACCESS_OP_READ_CHR){char s[200];xSemaphoreTake(lock,portMAX_DELAY);snprintf(s,sizeof s,"{\"v\":1,\"target\":\"%s\",\"maxBytes\":%lu,\"received\":%lu,\"busy\":%u,\"committed\":%u}",CONFIG_IDF_TARGET,(unsigned long)(slot(0)?slot(0)->size:0),(unsigned long)(owner==2?received:0),busy,committed);xSemaphoreGive(lock);return os_mbuf_append(ctxt->om,s,strlen(s))==0?0:BLE_ATT_ERR_INSUFFICIENT_RES;}
 uint8_t data[512];uint16_t n=0;if(ble_hs_mbuf_to_flat(ctxt->om,data,sizeof data,&n)||!n)return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
 bool ok=false,reboot=false;xSemaphoreTake(lock,portMAX_DELAY);
 if(data[0]==1&&n==17){authorized=equal(data+1,token,16);ok=authorized;}
 else if(authorized){switch(data[0]){
 case 2:if(n==5){ok=begin_update(2,le32(data+1));if(ok)digest_parts=0;}break;
 case 3:if(n==18&&busy&&owner==2&&data[1]<2){memcpy(expected_ble+16*data[1],data+2,16);digest_parts|=1<<data[1];ok=true;}break;
 case 4:if(n>5)ok=write_update(2,le32(data+1),data+5,n-5);break;
 case 5:if(n==1&&digest_parts==3){ok=finish_update(2,expected_ble);reboot=ok;}break;
 case 6:if(n==1&&busy&&owner==2){abort_update();ok=true;}break;
 case 7:if(n==1){ok=resume_previous();reboot=ok;}break;
 }}xSemaphoreGive(lock);if(reboot)schedule_reboot();return ok?0:BLE_ATT_ERR_UNLIKELY;
}
static const struct ble_gatt_chr_def chars[]={
 {.uuid=&cmd_uuid.u,.access_cb=ble_access,.flags=BLE_GATT_CHR_F_WRITE|BLE_GATT_CHR_F_WRITE_ENC|BLE_GATT_CHR_F_WRITE_AUTHEN},
 {.uuid=&status_uuid.u,.access_cb=ble_access,.flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_READ_ENC|BLE_GATT_CHR_F_READ_AUTHEN},{0}};
static const struct ble_gatt_svc_def svcs[]={{.type=BLE_GATT_SVC_TYPE_PRIMARY,.uuid=&service_uuid.u,.characteristics=chars},{0}};
static void advertise(void);
static int gap_event(struct ble_gap_event *e,void *arg){switch(e->type){case BLE_GAP_EVENT_CONNECT:authorized=false;if(e->connect.status)advertise();break;case BLE_GAP_EVENT_DISCONNECT:xSemaphoreTake(lock,portMAX_DELAY);authorized=false;if(busy&&owner==2)abort_update();xSemaphoreGive(lock);advertise();break;case BLE_GAP_EVENT_ADV_COMPLETE:advertise();break;case BLE_GAP_EVENT_PASSKEY_ACTION:if(e->passkey.params.action==BLE_SM_IOACT_DISP){struct ble_sm_io io={0};io.action=BLE_SM_IOACT_DISP;io.passkey=passkey;ble_sm_inject_io(e->passkey.conn_handle,&io);}break;default:break;}return 0;}
static void advertise(void){struct ble_hs_adv_fields f={0};f.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;f.uuids128=&service_uuid;f.num_uuids128=1;f.uuids128_is_complete=1;if(ble_gap_adv_set_fields(&f))return;struct ble_hs_adv_fields r={0};const char *name=ble_svc_gap_device_name();r.name=(const uint8_t*)name;r.name_len=strlen(name);r.name_is_complete=1;ble_gap_adv_rsp_set_fields(&r);struct ble_gap_adv_params p={0};p.conn_mode=BLE_GAP_CONN_MODE_UND;p.disc_mode=BLE_GAP_DISC_MODE_GEN;ble_gap_adv_start(addr_type,NULL,BLE_HS_FOREVER,&p,gap_event,NULL);}
static void ble_sync(void){if(ble_hs_id_infer_auto(0,&addr_type)==0)advertise();}
static void host_task(void *arg){nimble_port_run();nimble_port_freertos_deinit();}
static void start_ble(void){passkey=random_passkey;printf("BLE passkey=%06" PRIu32 "\n",passkey);ESP_ERROR_CHECK(nimble_port_init());ble_svc_gap_init();ble_svc_gatt_init();if(ble_svc_gap_device_name_set(device_name)||ble_gatts_count_cfg(svcs)||ble_gatts_add_svcs(svcs))abort();ble_hs_cfg.sync_cb=ble_sync;ble_hs_cfg.sm_io_cap=BLE_HS_IO_DISPLAY_ONLY;ble_hs_cfg.sm_mitm=1;ble_hs_cfg.sm_sc=1;ble_hs_cfg.sm_bonding=0;nimble_port_freertos_init(host_task);}
#endif
void app_main(void){
 /* Never erase NVS automatically: it may contain application data. */
 ESP_ERROR_CHECK(nvs_flash_init());ESP_ERROR_CHECK(nvs_flash_init_partition("fs_meta"));ESP_ERROR_CHECK(nvs_open_from_partition("fs_meta","fs_recovery",NVS_READWRITE,&prefs));nvs_get_u8(prefs,"previous",&previous);
 lock=xSemaphoreCreateMutex();if(!lock)abort();
 /* Initialize only on first boot, retain the same credentials across Recovery sessions. */
 credentials_t creds={0};size_t clen=sizeof creds;esp_err_t err=nvs_get_blob(prefs,"credentials_v1",&creds,&clen);
 if(err==ESP_ERR_NVS_NOT_FOUND){
   bootloader_random_enable();esp_fill_random(creds.token,sizeof creds.token);esp_fill_random(creds.password,sizeof creds.password);creds.passkey=esp_random()%1000000;bootloader_random_disable();
   ESP_ERROR_CHECK(nvs_set_blob(prefs,"credentials_v1",&creds,sizeof creds));ESP_ERROR_CHECK(nvs_commit(prefs));
 }else{ESP_ERROR_CHECK(err);if(clen!=sizeof creds||creds.passkey>999999)abort();}
 memcpy(token,creds.token,sizeof token);random_passkey=creds.passkey;
 for(unsigned i=0;i<12;i++)snprintf(ap_password+2*i,3,"%02x",creds.password[i]);
 for(unsigned i=0;i<16;i++)snprintf(token_hex+2*i,3,"%02x",token[i]);
 uint8_t mac[6];ESP_ERROR_CHECK(esp_efuse_mac_get_default(mac));
 snprintf(device_name,sizeof device_name,"FS-%02X%02X%02X%02X%02X%02X",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
 /* Physical console remains a recovery route if the owner loses the saved credentials. */
 printf("\nFlasher Recovery v0.2.1 token=%s target=%s device=%s\n",token_hex,CONFIG_IDF_TARGET,device_name);
 if(xTaskCreate(watchdog_task,"fs_timeout",2048,NULL,3,NULL)!=pdPASS)abort();
#if CONFIG_FS_WIFI
 start_wifi();
#endif
#if CONFIG_FS_BLE
 start_ble();
#endif
}
