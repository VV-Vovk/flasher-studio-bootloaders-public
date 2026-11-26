"""Assemble an auditable, conservative notice inventory, not redistribution approval."""
import argparse, hashlib, json, pathlib, re
P=pathlib.Path
def assemble(audit,idf,dest):
    audit=P(audit).resolve();idf=P(idf).resolve();dest=P(dest)
    idx=json.loads((audit/'notice-text-index.json').read_text())
    if idx['sdkCommit']!='f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0':raise ValueError('SDK mismatch')
    sections=['Flasher Studio ESP Recovery — THIRD-PARTY NOTICES (DRAFT; LOCAL TEST ONLY)\nThis is a conservative SDK/toolchain notice inventory; it may contain licenses of unused components. It is not approval for redistribution. Do not redistribute the resulting firmware while review is on HOLD.\nSDK commit: '+idx['sdkCommit']]
    for group in ('sdk','toolchain'):
        for item in idx[group]:
            if 'notice' not in item:raise ValueError('Incomplete original notice: '+item['path'])
            path=(audit/item['notice']).resolve()
            if not path.is_relative_to(audit/'notices'):raise ValueError('notice path')
            data=path.read_bytes()
            if len(data)!=item['size'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('notice checksum '+item['path'])
            sections.append('===== '+group+'/'+item['path']+' =====\n'+data.decode('utf-8',errors='strict'))
    # The upstream COPYING file explicitly points to the README for BSD terms.
    for rel in ['components/wpa_supplicant/README']:
        text=(idf/rel).read_text()
        if 'Redistribution and use in source and binary forms' not in text:raise ValueError('Missing BSD terms')
        sections.append('===== sdk/'+rel+' =====\n'+text)
    # TLSF upstream uses SPDX-only headers and no standalone LICENSE.
    hdr=(idf/'components/heap/tlsf/include/tlsf.h').read_text()
    if '2006-2016 Matthew Conte' not in hdr or 'SPDX-License-Identifier: BSD-3-Clause' not in hdr:raise ValueError('TLSF upstream changed')
    sections.append('===== TLSF =====\nCopyright (c) 2006-2016 Matthew Conte\nBSD-3-Clause\n'+
        'Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:\n'
        '1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.\n'
        '2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.\n'
        '3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.\n'
        'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.')
    # Preserve the actual SPDX inventory, including file-level copyright and unknowns.
    spdx=(audit/'application.spdx').read_text()
    if 'SPDXVersion:' not in spdx:raise ValueError('Missing SPDX inventory')
    sections.append('===== Build SPDX inventory =====\n'+spdx)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text('\n\n'.join(sections)+'\n',encoding='utf-8')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('audit');a.add_argument('idf');a.add_argument('dest');v=a.parse_args();assemble(v.audit,v.idf,v.dest)
