// 内部验收使用的本机代理：SSH 隧道上游始终校验原服务的 CA 和主机身份。
import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';
import tls from 'node:tls';
const ca=fs.readFileSync('.local/ca.pem');
const origin='https://192.168.1.169:9443';
const local='http://127.0.0.1:19943';
const aliases=[['https://192.168.1.169:9443','http://127.0.0.1:19943'],['https://192.168.1.169:8443','http://127.0.0.1:18843']];
function localize(text){for(const [remote,alias] of aliases)text=text.replaceAll(remote,alias);return text;}
function upstreamOrigin(value){return aliases.find(([,alias])=>alias===value)?.[0]||value;}
function options(port){return {host:'127.0.0.1',port,ca,servername:'192.168.1.169',checkServerIdentity:(_,cert)=>tls.checkServerIdentity('192.168.1.169',cert)}}
function serve(port,remote,rewrite){
  const server=http.createServer((req,res)=>{
    const headers={...req.headers,host:'192.168.1.169:'+(rewrite?9443:8443),'accept-encoding':'identity'};
    if(headers.origin)headers.origin=upstreamOrigin(headers.origin);
    const upstream=https.request({...options(remote),path:req.url,method:req.method,headers},response=>{
      const chunks=[];response.on('data',chunk=>chunks.push(chunk));response.on('end',()=>{
        let body=Buffer.concat(chunks);const result={...response.headers};delete result['transfer-encoding'];
        if(/(html|javascript|json)/.test(result['content-type']||''))body=Buffer.from(localize(body.toString()));
        if(result.location)result.location=localize(result.location);
        if(result['access-control-allow-origin'])result['access-control-allow-origin']=localize(result['access-control-allow-origin']);
        result['content-length']=body.length;res.writeHead(response.statusCode,result);res.end(body);
      });
    });upstream.on('error',error=>{res.writeHead(502);res.end(error.message)});req.pipe(upstream);
  });
  server.on('upgrade',(req,socket,head)=>{
    const upstream=tls.connect(options(remote),()=>{
      const headers={...req.headers,host:'192.168.1.169:'+(rewrite?9443:8443),origin:upstreamOrigin(req.headers.origin)};
      upstream.write(`${req.method} ${req.url} HTTP/1.1\r\n`+Object.entries(headers).map(([k,v])=>`${k}: ${v}`).join('\r\n')+'\r\n\r\n');
      if(head.length)upstream.write(head);socket.pipe(upstream);upstream.pipe(socket);
    });upstream.on('error',()=>socket.destroy());socket.on('error',()=>upstream.destroy());
  });server.listen(port,'127.0.0.1');
}
serve(19943,19443,true);serve(18843,18443,false);
console.log('TLS 校验验收代理已启动，仅监听本机回环地址');
