self.addEventListener('push',event=>{
  let data={};try{data=event.data?event.data.json():{};}catch{}
  event.waitUntil(self.registration.showNotification(data.title||'SatBox AOS通知',{
    body:data.body||'Pass一覧を確認してください。',tag:data.tag||'satbox-aos',
    data:{url:data.url||self.registration.scope},renotify:false
  }));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    const scope=new URL(self.registration.scope),url=new URL(event.notification.data?.url||scope.href,scope);
    if(url.origin!==scope.origin||!url.pathname.startsWith(scope.pathname))return;
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows){if(client.url===url.href){await client.focus();return;}}
    await self.clients.openWindow(url.href);
  })());
});
