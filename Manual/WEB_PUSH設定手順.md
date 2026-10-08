[日本語](WEB_PUSH設定手順.md) | [English](Web_Push_Setup_Guide_EN.md)

# SatBox Cloud Web Push設定・動作確認

改訂日：2026年10月8日

## 1. この手順の役割

[サーバー設置手順](サーバー設置手順.md)で画面をHTTPS公開した後に使用します。
本書はWeb Pushの鍵、端末登録、テスト、配信処理とトラブル確認を詳しく説明します。
画面上の音声アナウンスとは別機能です。画面を閉じた後のPushにはサーバーの送信処理が必要です。
コマンドはManualではなくsatbox-cloud直下で実行します。

## 2. 必要な環境

- 信頼できる証明書で公開したHTTPS URL。
- Web Push・Service Workerに対応するブラウザーと、ブラウザー／OSの通知許可。
- サーバーのPython環境、依存ライブラリ、Pushサービスへの外向きHTTPS通信。
- 予定生成と送信を継続実行する、事業者が許可したCronまたは常駐処理。

スマートフォンから通常のHTTP LAN URL（例：http://192.168.1.10:8081）で登録できません。
iPhone／iPadではiOS／iPadOS 16.4以降のホーム画面Webアプリでの対応を確認し、
ホーム画面に追加したアプリから開いて通知を許可します。端末・ブラウザーの対応も確認してください。
詳細：[AppleのWeb Push説明](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)。

依存ライブラリの導入例（Linux）：

```bash
.venv/bin/python -m pip install -r requirements-web.txt
```

既存XSERVER環境でrequirements-xserver.txtを使用している場合は、設置手順に従ってください。
Windowsでは`.venv/bin/python`を`.\.venv\Scripts\python.exe`に読み替えます。

## 3. 非公開保存先と鍵を設定

Web、初期設定、予定生成、送信で同じ設定ファイルと非公開データフォルダーを使用します。
以下のパス・ドメイン・連絡先を実際の値へ置換してください。

```bash
.venv/bin/python setup_push.py --base-url https://YOUR-HOST/satbox --subject mailto:YOUR-EMAIL --config web-qth.json --data-dir /home/ACCOUNT/satbox-data
```

- `--base-url`：実際のHTTPS公開URL。サブパスがある場合は含めます。
- `--subject`：運用者の連絡先（mailto:形式）。
- `--config`／`--data-dir`：Webとworkerも同じ値を使用します。

setup_push.pyは設定を保存するだけで、通知を送信しません。
再実行時は既存のVAPID鍵と暗号化鍵を維持し、公開URLと連絡先を更新します。
非公開フォルダー内の`push-config.json`、`vapid-private.pem`、`push-encryption.key`、
`users.sqlite3`等を一緒にバックアップします。鍵を消したり別環境の鍵で上書きしないでください。
DBと鍵はHTML公開フォルダーに置かず、Linuxのアクセス権やWindows ACLで保護します。

## 4. HTTPS公開とService Worker

CGI方式は設置手順の公開入口を使用し、通知のためにWaitressを追加起動する必要はありません。
WSGI方式は信頼するHTTPSプロキシの背後で次のように起動します。

```bash
.venv/bin/python serve_web.py --port 8080 --config web-qth.json --data-dir /home/ACCOUNT/satbox-data
```

serve_web.pyは127.0.0.1で待受し、同じホストのHTTPSプロキシ1段を想定します。
nginxの既存HTTPS serverブロック内へ追加する例：

```nginx
location = /satbox { return 301 /satbox/; }
location /satbox/ {
    proxy_pass http://127.0.0.1:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Prefix /satbox;
}
```

証明書と公開先はサーバー環境に合わせます。Flask開発サーバーを本番公開に使用しません。
登録時はHTTPSと設定されたホスト・ポートの一致を検査するため、別名ドメインでは登録できません。
`/satbox/`設置時は`/satbox/service-worker.js`がJavaScriptとして配信され、scopeは`/satbox/`です。
認証画面、端末登録、Service Workerの経路をCDN等の共有キャッシュに保存しないでください。

## 5. 予定生成と送信

常駐が許可される環境では、別々のターミナル／サービスで実行します。

```bash
.venv/bin/python prepare_notifications.py --config web-qth.json --data-dir /home/ACCOUNT/satbox-data --loop
```

```bash
.venv/bin/python send_notifications.py --config web-qth.json --data-dir /home/ACCOUNT/satbox-data --loop
```

予定生成は5秒ごとにTLE・QTH・選択等の変更を確認し、変更時または15分経過時に処理します。
正常な軌道計算キャッシュは30分です。送信は1秒周期で保存済みキューとテスト予約を確認し、軌道計算をしません。
共有サーバーでは許可された実行方式を選びます。Cron単発は`--loop`を外し、作業ディレクトリと
Pythonの絶対パスを指定します。1分周期ならその待ち時間と通信遅延が加わります。
Linuxのnotification_workers.shも使用できます。操作は[サーバー設置手順](サーバー設置手順.md)を参照してください。
再起動後の自動復帰・ログ管理はOSや事業者の機能で設定します。
`plan_notifications.py --all`は手動の予定確認用で、通知を送信しません。

## 6. ユーザー設定と端末登録

1. 実際のHTTPS公開URLでログインし、QTHと地域タイムゾーンを確認します。
2. 「衛星選択」で観測対象を保存します。
3. 「通知設定」で通知衛星、最低最大仰角、AOS前の時間、通知時間帯を保存します。
4. 「通知予定」で予定を確認します。条件外や送信時刻を過ぎたPassは新規予定に入りません。
5. 「通知端末登録」で端末名を入力し、「この端末の通知を登録」を押して許可します。
6. 別の端末も、その端末のブラウザーでログインして個別に登録します。

同じブラウザーのSubscriptionは1ユーザーだけに登録できます。
共有端末でアカウントを替えるときは元のユーザーで登録を解除します。
解除は「この端末の通知を解除」、または登録済み端末の解除ボタンを使用します。
英語表示の場合は対応する英語ラベルを使用してください。

## 7. テスト通知と繰り返し

通知設定画面のテストで、登録済み全端末への配信を確認できます。

- 繰り返し：1～5回。待ち時間：1～15秒。初期値は3回・7秒。
- 通常通知とテストに共通する設定です。テストボタンで回数と待ち時間を保存します。
- 他の未保存の通知条件は、テストボタンでは保存しません。
- テストは1ユーザーにつき1分に1回。通知時間帯や仰角条件には依存しません。
- 送信workerが必要です。120秒を超えた古いテスト予約は破棄します。

通知音はブラウザー・OS・端末設定に従います。画面を閉じた状態やロック画面でも確認してください。
全回数の表示・鳴動や正確な音間隔を保証する機能ではありません。
画面の日本語／英語切替とPush本文の言語は別で、現行Push本文は日本語です。

## 8. 実際のPassで確認

通知ONの衛星について、送信予定時刻がこれからのPassを選びます。
通知時刻はAOSから設定分数を引いた時刻で、時間帯もその時刻のQTH地域時刻で判定します。
受信通知をタップし、本人のPass詳細が開くことを確認します。
ログアウト中はログイン後に詳細へ戻り、他ユーザーの詳細は404になります。
2端末で受信を確認し、1端末の登録解除後は残りだけが受信することも確認します。
画面音声はPushとは別で、事前音声はPush予定より30秒後、AOS音声はAOS時刻です。

## 9. 配信期限・失敗・保存

送信は予定時刻から120秒以内、かつAOS後5秒の猶予以内などの条件を満たす場合に限ります。
停止後に古い通知を一斉送信しません。送信予定時刻より後に登録した端末にも配信しません。
通常通知は成功ごとに次回時刻を保存し、設定回数まで期限内で繰り返します。
404／410は無効な端末登録を削除します。429／5xx／通信失敗は期限内で最大3試行とします。
Pushサービスの受付成功は端末の表示・音を保証しません。受付後・DB記録前の異常終了では再送の可能性があります。
通知のtagはPassと繰り返し回数に対応します。OS側の通知集約・抑制にも左右されます。
Pass詳細はLOSから7日間を保存期間とし、次回予定再生成時に古い記録を削除します。

## 10. トラブル確認と更新

| 症状 | 確認内容 |
| --- | --- |
| HTTPSを要求される | HTTPS URL、証明書、CGI／プロキシのHTTPS認識 |
| 公開URLと違うと表示される | push-config.jsonのbase_urlと実際のホスト・ポート |
| 設定されていない／ユーザーが見つからない | Web・setup・workerの設定と非公開データ先の一致 |
| 端末登録できない | ブラウザー対応、通知許可、他ユーザーの登録、登録上限 |
| テストが来ない | 送信worker、予約からの経過時間、外向き通信、ログ、OS通知設定 |
| 通常通知だけ来ない | 通知ON、仰角、地域時間帯、送信予定、予定生成、期限 |
| 回数や音が違う | AOSまでの残り時間、通信遅延、OSの通知集約・省電力・音設定 |
| クリック先が違う | base_urlのサブパス、Service Workerのscope、プロキシ経路 |

コード更新後は対象の常駐Web／workerを再起動し、ブラウザーを再読み込みします。
CGI方式の更新手順は設置手順に従います。移設時はDBと鍵をまとめて保持し、公開URLを更新します。
異なるオリジンに移した場合は端末登録をやり直してください。
本書の整備では実通知送信や端末登録は実行していません。実環境で上記の確認を行ってください。

## 11. 関連文書

- [サーバー設置手順](サーバー設置手順.md)
- [開発仕様書](開発仕様書.md)
- [Push API（MDN）](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [pywebpush](https://github.com/web-push-libs/pywebpush)
