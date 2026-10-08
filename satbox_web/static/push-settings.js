(() => {
  const config=window.satboxPush, status=document.getElementById('push-status');
  let interacted=false;
  const permissionState=()=>('Notification' in window ? Notification.permission || '不明' : '未対応');
  const supported=window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const post=async(url,values)=>{
    const response=await fetch(url,{method:'POST',credentials:'same-origin',body:new URLSearchParams({csrf_token:config.csrf,...values})});
    if(response.redirected) throw new Error('ログインし直してください。');
    let result; try{result=await response.json();}catch{throw new Error('HTTPS公開URLとサーバー設定を確認してください。');}
    if(!response.ok)throw new Error(result.error||'操作に失敗しました。');return result;
  };
  const registration=async()=>{
    await navigator.serviceWorker.register(config.worker,{scope:config.scope});
    return navigator.serviceWorker.ready;
  };
  const publicKey=()=>Uint8Array.from(atob(config.key.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-config.key.length%4)%4)),c=>c.charCodeAt(0));
  if(!supported){status.textContent='HTTPSで開き、Web Push対応ブラウザーを使用してください。';document.getElementById('push-register').disabled=true;document.getElementById('push-unsubscribe').disabled=true;}
  else {status.textContent='通知許可：'+permissionState()+'。登録状態を確認中…'; registration().then(async reg=>{const sub=await reg.pushManager.getSubscription();const result=sub?await post(config.current,{endpoint:sub.endpoint}):null;if(!interacted)status.textContent=(result?.id?'この端末は登録済みです。':'このユーザーには未登録です。')+' 通知許可：'+permissionState();}).catch(e=>{if(!interacted)status.textContent=e.message+' 通知許可：'+permissionState();});}
  document.getElementById('push-register').addEventListener('click',async()=>{
    interacted=true;let stage='通知許可';
    try{
      if(!supported||!config.key)throw new Error('HTTPSとWeb Push設定を確認してください。');
      // Request permission directly from the user gesture.
      status.textContent='通知の許可を確認しています。現在：'+permissionState();
      const permission=await Notification.requestPermission();
      if(permission!=='granted')throw new Error('ブラウザーの応答：'+permission+'。'+(permission==='denied'?'通知が拒否されています。Chromeアプリ全体と、このサイトの通知設定を確認してください。':'通知許可が確定していません。許可画面やアドレス欄の通知アイコンを確認してください。Chromeアプリ全体の通知も有効にしてください。'));
      stage='Service Worker起動';status.textContent='通知は許可済みです。通知機能を準備中…';
      const reg=await registration();let sub=await reg.pushManager.getSubscription(),created=false;
      stage='Pushサービス登録';status.textContent='通知の受信先を登録中…';
      if(!sub){sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:publicKey()});created=true;}
      stage='サーバーへの端末保存';status.textContent='端末情報をサーバーへ保存中…';
      try{await post(config.register,{subscription:JSON.stringify(sub),label:document.getElementById('push-label').value});}
      catch(e){if(created)await sub.unsubscribe();throw e;}
      location.reload();
    }catch(e){status.textContent='['+stage+'] '+e.message+'（現在の通知許可：'+permissionState()+'）';}
  });
  document.getElementById('push-unsubscribe').addEventListener('click',async()=>{
    try{
      const reg=await registration(),sub=await reg.pushManager.getSubscription();
      if(sub){const result=await post(config.current,{endpoint:sub.endpoint});if(result.id)await post(config.remove,{id:result.id});else throw new Error('このユーザーの登録ではありません。登録元のユーザーで解除してください。');await sub.unsubscribe();}
      location.reload();
    }catch(e){status.textContent=e.message;}
  });
  document.querySelectorAll('.push-remove').forEach(button=>button.addEventListener('click',async()=>{
    try{await post(config.remove,{id:button.dataset.id});location.reload();}catch(e){status.textContent=e.message;}
  }));
})();
