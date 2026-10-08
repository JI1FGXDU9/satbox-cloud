[日本語](README_jp.md) | [English](README.md)

# SatBox Cloud

SatBox Cloudは、ユーザーごとの観測地点（QTH）からアマチュア衛星の通過を予測するWebアプリケーションです。ブラウザーで利用する画面、データベース、ユーザー登録、Web Push通知、音声アナウンス、衛星地図を備えています。

主な機能は次のとおりです。

- ユーザー登録、メールアドレスの保存、QTH設定
- 衛星選択と今後24時間・48時間のPass予測
- AOS／LOS時刻、最大仰角、方位角、カウントダウンの表示
- 衛星の位置と可視範囲を確認できる地図
- AOS通知条件の設定、複数端末の登録、テスト通知
- ブラウザー表示中の音声アナウンス
- 管理画面でのユーザー一覧・メールアドレス表示、権限変更、一般ユーザーの削除、NASA.ALLの更新
- 日本語・英語表示

設置・運用手順は[サーバー設置手順](サーバー設置手順.md)、通知の設定は[Web Push設定手順](WEB_PUSH設定手順.md)を参照してください。コマンドはManualフォルダーではなくsatbox-cloud直下で実行します。

## 初期開発時の軌道計算・実機比較の記録

以下は初期開発時の記録です。記載されている実験用スクリプトやサンプルは、現在の公開用フォルダーには含まれません。現在の設置・運用には上記の手順書を使用してください。

## Windowsで実行

このフォルダーでPowerShellを開き、次を実行します。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe predict.py example.json
.\.venv\Scripts\python.exe predict.py example.json --horizon 5
```

`py`にPythonが登録されていなければ、Python 3.11以上をインストールしてから実行します。
計算時の通信は不要です。TLEを自動取得・更新しません。

## 入力

example.jsonは過去のISSの固定TLEを使う動作確認専用例です。
現在の予測には使わず、実機SatBoxと同じTLE・QTH・日時に置き換えてください。

* satellite_name：衛星名
* tle_line1 / tle_line2：末尾チェックサムを含む69文字のTLE。空白を保存すること。
* latitude_deg：WGS84測地緯度、北が正、南が負（度）
* longitude_deg：東が正、西が負（度）
* altitude_m：WGS84楕円体からの高さ（m）。海抜高度との違いに注意。
* start_utc：ISO 8601日時。ZまたはUTCオフセットが必須。内部はUTCへ変換。
* duration_hours：予測範囲（時間）、正の値
* horizon_deg：AOS/LOS判定の幾何学的仰角（度）、既定0。CLIで上書き可能。

## 出力と比較条件

AOS日時・AZ、最大仰角の日時・EL、LOS日時・AZ、Pass時間（秒）を表示します。
UTC日時はミリ秒、角度と時間は小数3桁で表示しますが、表示桁数は精度保証ではありません。
内部の丸め前の結果はPassデータとして保持します。方位角は北0度、東90度。
大気差補正、地形・建物による遮蔽、地平線の俯角補正は適用しません。
探索はSkyfieldのfind_eventsを使用し、複数の極大がある場合は最も高いものを採用します。
範囲内にAOSとLOSが揃う完全なPassだけを出力します。開始時・終了時に可視なら注意を表示します。
必要なら開始を早め、終了を遅らせてください。常時可視の衛星には完全なPassが出ない場合があります。

Skyfield EarthSatelliteのSGP4既定はWGS72、観測地点はWGS84です。
時刻変換はSkyfield同梱データを使い、外部の地球回転補正データは取得しません。
実機の定数系、座標変換、horizon、高度基準、時間刻み、丸めを確認して比較してください。
古いTLEから遠い日時を予測すると実際の軌道との誤差が増えます。
TLE形式・チェックサム・衛星番号を検査し、SGP4エラーは終了コード2で報告します。

## 分離したモジュール

* observer.py：観測地点
* orbit.py：TLE・SGP4・AZ/EL
* passes.py：Pass検索と結果データ
* display.py：結果表示
* predict.py：JSON入力とCLI

将来のWebからもCLIを通さず呼び出せます。

```python
from datetime import datetime, timedelta, timezone
from satbox_orbit import Observer, Orbit, find_passes

observer = Observer(latitude_deg, longitude_deg, altitude_m)
orbit = Orbit(name, line1, line2, observer)
start = datetime(2026, 10, 7, tzinfo=timezone.utc)
result = find_passes(orbit, start, start + timedelta(hours=24), horizon_deg=0)
az, el = orbit.angles(start)  # 固定日時のAZ/EL比較も可能
```

## 検証

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

固定TLEに対するhorizon交差、最大仰角、期間境界、UTC変換、入力エラーを検証します。
これはESP32-S3版との一致確認を代替しません。実機との比較は未実施です。

参考： https://rhodesmill.org/skyfield/earth-satellites.html

## NASA.ALLからISSの比較入力を作成

追加ライブラリは不要です。ダウンロードはprepare_input.pyを明示的に実行した時だけ行います。
計算エンジンおよびpredict.pyは引き続きオフラインで動作します。

```powershell
.\.venv\Scripts\python.exe prepare_input.py
.\.venv\Scripts\python.exe predict.py iss-qth.json
```

既定値：ISS（NORAD 25544）、緯度8.209000、経度123.860001、高度20m、horizon 0度、開始は実行時刻のUTC、期間24時間。
画像の「標高20m」をそのまま入力値に使用しています。厳密には実機の高度基準の確認が必要です。

先ほどのSatBox画像と同じ2026年10月7日（UTC+8）の一日を計算する例：

```powershell
.\.venv\Scripts\python.exe prepare_input.py --start "2026-10-07T00:00:00+08:00"
.\.venv\Scripts\python.exe predict.py iss-qth.json --horizon 0
```

取得済みデータを再利用する場合（再ダウンロードしない）：

```powershell
.\.venv\Scripts\python.exe prepare_input.py --file nasa.all --start "2026-10-07T00:00:00+08:00"
```

ダウンロード元の既定は https://www.amsat.org/tle/current/nasa.all です。
SatBoxの配信元はソース未確認なので、同じURLと断定していません。必要なら--urlで変更できます。
取得ファイルをnasa.all、比較入力をiss-qth.json、URL・保存日時・Last-Modified・SHA256・TLE epochをiss-qth.source.jsonに保存します。
これらの名前は再実行で上書きされます。比較に使ったファイルは事前に別名で保管してください。
TLEが更新されると過去の画面との結果が変わる可能性があるため、厳密な比較には同一のTLEが必要です。

今回保存した固定データでの確認結果（UTC+8に換算）：
AOS 2026-10-07 15:55:56.795、AOS AZ 2.438度、最大仰角7.375度、
最大仰角時刻15:59:54.347、LOS16:03:50.947、LOS AZ97.089度、Pass時間474.153秒。
SatBox画像：AOS15:55:56、LOS16:03:50、AOS AZ2.5度、最大仰角7.4度。
表示上は近い結果ですが、実機のTLE・horizon・高度基準・丸めが未確認のため、正式な一致判定はまだ行いません。
## 衛星名で選択（AO-73の比較）

```bat
prepare_input.py --satellite AO-73 --file nasa.all --start "2026-10-07T00:00:00+08:00"
predict.py ao-73-qth.json --horizon 0
```

--satelliteはNASA.ALL中の衛星名を指定します（大小文字は区別しません）。
--noradとは同時に指定できません。どちらも省略するとISSです。
出力名は衛星名に応じてao-73-qth.jsonなどになります。--outputで変更できます。
--fileを省略するとNASA.ALLを再ダウンロードします。
今回保存したAO-73比較データはISSと同じ固定NASA.ALLを使っています。
## ステップ2：SatBoxとPythonの比較

```bat
compare.py compare-ao-73-example.json
compare.py compare-iss-example.json
```

この2ファイルは以前の画像による表示値とAMSATのTLEを使った動作確認用です。
SatBox側の正確なTLEは未確認です。正式な一致判定用データではありません。
コピーして別名で保存し、以下を実機の正確な入力値に変更してください。

satellite_name, tle_line1, tle_line2, latitude_deg, longitude_deg, altitude_m,
horizon_deg、およびsatbox内のaos、los、maxel_deg。

satboxの入力例：

"satbox": {
  "aos": "2026-10-07T07:07:51Z",
  "los": "2026-10-07T07:19:47Z",
  "maxel_deg": 42.8
}

ローカル日時なら"2026-10-07T15:07:51+08:00"のようにUTCオフセットを付けます。
日付なしの時刻、タイムゾーンなしの日時は受け付けません。UTCへ変換して比較します。
comparison_noteもデータの出所に合わせて変更してください。

差の定義はPython値－SatBox値です。正ならPythonの時刻が遅い、または最大仰角が高いことを示します。
差の計算には表示時に丸める前のPython値を使います。
補正値・オフセットは適用しません。合否の許容差も自動設定しません。

参照AOSの30分前から参照LOSの30分後までを検索し、参照期間と重なる完全なPassが1つだけなら比較します。
候補が0件または複数ならエラーにして、別Passを勝手に選びません。
必要なら--search-margin-minutes 60などで探索範囲だけを広げられます。
これは計算時刻への補正ではありません。

原因を調べる際の確認事項：
1. SatBoxで使用したTLE2行を文字単位で一致させる。取得日時だけの一致では不十分。
2. 日付、UTCオフセット、夏時間、UTCへの変換を確認する。
3. 緯度経度の符号、高度のm単位、海抜と楕円体高の違いを確認する。
4. horizonが幾何学的仰角なのか、大気差や地形を含むのかを確認する。
5. SatBoxのSGP4実装、WGS72/WGS84等の定数系、TLE解釈を確認する。
6. 数値型（float/double）、最大仰角の探索、AOS/LOSの探索刻みを確認する。
7. 秒や角度の表示が切り捨てか四捨五入かを確認する。

コマンドはTLE、QTH、horizon、ライブラリ版、Python側の定数・高度条件を表示します。
SatBox側の詳細が未提供なら、差の原因は断定しません。
軌道計算が十分一致するまでWebサービスを開発しません。
ステップ2ではSkyfieldで検出したAOS/LOS候補の前後を二分探索し、幾何学的仰角がhorizonを横切る区間を1ms以下まで詰めます。これは物理精度の保証や補正値ではありません。検索範囲による時刻の変動を抑えるための数値探索です。旧版の出力とは秒未満が変わる場合があります。最大仰角の探索は引き続きSkyfieldを使います。

比較結果は既定でローカルUTC+8表示です。compare.py compare-ao-73-example.json --utc-offset 0でUTC表示に戻せます。--utc-offsetは表示だけを変更し、入力の日時を解釈し直しません。ローカル入力は必ず+08:00等を付けてください。

AOS方位角比較：satbox内にaos_az_deg（例AO-73は156.3）を追加します。北0度・東90度、0以上360未満。省略時もPythonのAOS AZは表示します。差はPython－SatBoxを-180以上180未満へ折り返した最短の符号付き角度です。各実装のAOS時刻における方位角を比較するので、AOS時刻差の影響も含みます。

## 複数衛星のPass予測

```bat
predict_multi.py multi-qth.json
predict_multi.py multi-qth.json --min-maxel 0
predict_multi.py multi-qth.json --satellites ISS AO-73 IO-86 --min-maxel 10
predict_multi.py multi-qth.json --start now
```

multi-qth.jsonは画像と同じ8衛星、QTH、2026年10月7日の一日、horizon=0、最低最大仰角10度です。
satellitesを省略するとTLEファイル内のすべての衛星が対象になります。
衛星名は大小文字を区別しません。不明な名前や曖昧な重複はエラーになります。
tle_fileの相対パスはJSONファイルのあるフォルダーを基準に解決します。
ローカルTLEを使用し、このコマンドはダウンロードしません。

horizon_degはAOS/LOSを決める仰角、min_maxel_degはPassを表示するための最大仰角の下限です。
最大仰角が下限以上なら表示します。判定は表示の丸め前の値を使用します。
内部UTC、表示は既定UTC+8（--utc-offset 0でUTC）。全衛星のPassをAOS順に並べます。
開始・終了で切れるPassは従来どおり除外し、衛星名付きの注意を表示します。
1衛星のTLEや軌道計算でエラーが起きた場合、他の衛星を計算してエラーを明記し、終了コード1を返します。
入力設定エラーは終了コード2です。エラーのある出力は全衛星分が揃った結果ではありません。

モジュール：catalog.pyはTLE読み込み・選択、multiple.pyは複数衛星の計算・フィルター・並べ替え、predict_multi.pyはCLIです。
将来のWebからはread_catalog、select_records、predict_multipleを直接呼び出せます。
ユーザー登録・通知・Web機能は作成していません。
## Web試作版（固定QTH・ユーザー登録なし）

まず、今までコマンドを動かしているPythonでFlaskをインストールします。

```bat
python -m pip install -r requirements-web.txt
python web.py
```

pythonコマンドが使えない場合は、これまで使っているPythonの実行ファイルや仮想環境のpython.exeで同じコマンドを実行してください。
既存の仮想環境なら：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.venv\Scripts\python.exe web.py
```

ブラウザーで http://127.0.0.1:8080/ を開きます。終了はCtrl+Cです。
同じ家庭内LANのスマートフォンから試す場合：

```bat
python web.py --host 0.0.0.0
```

スマートフォンを同じWi-Fiにつなぎ、http://PCのLANアドレス:8080/ を開きます。
Windowsファイアウォールの確認が出た場合は、利用するプライベートネットワークでの接続を許可します。
PCのLANアドレスはipconfigで確認できます。この起動方法はローカル試作の確認用です。
Flask内蔵サーバーは本番公開用ではありません。ji1fgx.comへの公開には、サーバーのPython実行環境とWSGI等の構成確認が別途必要です。
参考： https://flask.palletsprojects.com/en/stable/server/

設定はweb-qth.jsonで行います。固定QTH、衛星、予測24時間、最低最大仰角10度、UTC+8が既定です。
過去の固定日付ではなく、アクセス時点から今後24時間を計算します。
現在時刻は1秒ごと、一覧は60秒ごとに更新します。AOS順で衛星名、AOS、MAXEL、LOSを表示します。
PCは表、スマートフォンは縦並びのカード表示です。

TLE更新日時は、tle_metadata_fileに指定した取得記録のSHA256が現在のNASA.ALLと一致するとき、配信元のLast-Modifiedを表示します。
ファイルのコピー日時や衛星ごとのTLE epochを更新日時と混同しません。
取得記録が不明なら不明と表示します。WebからTLEを自動取得・更新する機能はまだありません。
prepare_input.pyでNASA.ALLを更新した場合は、そのとき作られるsource.jsonをtle_metadata_fileに指定してください。

構成：satbox_web/app.py（Flaskアダプター）、templates（画面）、static/style.css（レスポンシブ書式）、web.py（起動）。
既存satbox_orbitの計算モジュールにはFlask依存を追加していません。
ユーザー登録、データベース、Web Push、通知、地図、ハードウェア制御は実装していません。
## 複数ユーザー版（2026-10-07）

起動中の旧web.pyはCtrl+Cで停止してから、次を実行してください。

```bat
python -m pip install -r requirements-web.txt
python web.py --host 0.0.0.0 --port 8081
```

PCは http://127.0.0.1:8081/ 、同じLANのスマートフォンは http://PCのIPアドレス:8081/ を開きます。
最初にログイン画面が開きます。「ユーザー登録」から登録してください。
登録情報はログインID、パスワード、コールサイン、緯度、経度、高度、タイムゾーン、グリッドロケーター、予測範囲（24/48時間）です。
パスワードは8～128文字。ログインIDとコールサインは別項目で、ログインIDは変更しません。
タイムゾーンは Asia/Manila（フィリピン）、Asia/Tokyo（日本）などの地域名を入力します。夏時間は地域の規則に従います。
グリッドは4/6/8文字で緯度・経度との一致を確認します。空欄なら6文字を自動計算します。
JI1FGX/DU9のQTH（8.209, 123.860001, 20 m）はPJ18WFです。
登録後は「QTH設定」で自分の設定を変更できます。別ユーザーはログアウト後に登録するか、別ブラウザー・プライベートウィンドウで試してください。
同じブラウザーの8080/8081はログインCookieを共有します。ポート違いで別ユーザーを比較する場合は別ブラウザーを使ってください。

### 保存とモジュール

- satbox_web/auth.py: 登録・ログイン・ログアウト・CSRF検証。Werkzeugのscryptでパスワードをハッシュ化。失敗10回で15分間ログイン制限。
- satbox_web/storage.py: SQLiteによるアカウント/QTH保存。更新対象はログイン済みのサーバー側ユーザーIDから決定。
- satbox_web/profile.py: QTH・タイムゾーン・Maidenheadグリッドの入力検証。
- satbox_web/cache.py: 既存のsatbox_orbit.multiple.predict_multipleを呼ぶ保存型Passキャッシュ。
- satbox_web/app.py/templates/static: Web表示。検証済みsatbox_orbitの計算コードは変更していません。

Windowsの既定保存先は %LOCALAPPDATA%\SatBoxCloud\設定ファイルパスの識別子\ です。
users.sqlite3（登録情報・パスワードハッシュ）、passes.sqlite3（Pass）、session.key（Cookie署名鍵）を保存します。
公開HTMLフォルダーには保存しません。2つのポートで同じ設定ファイルを使えば、同じアカウント・キャッシュ・署名鍵を利用します。
別の保存先は --data-dir "C:\任意の非公開フォルダー" または環境変数 SATBOX_DATA_DIR で指定できます。
データをバックアップする場合はサーバーを停止してから保存先フォルダー全体をコピーしてください。
session.keyを変更・削除すると既存のログインCookieは無効になります。パスワードは平文では保存しません。

### Passの効率的な計算

毎秒動くのはブラウザーのカウントダウンだけです。一覧の60秒更新は保存済みPassを使用します。
そのユーザーが画面を開いた時点でキャッシュがなければ、選択衛星について24/48時間のPassを事前計算します。
登録ユーザー全員を常時計算するループはありません。衛星選択・horizon・最低最大仰角は、現段階ではweb-qth.jsonの共通条件です。
キャッシュキーにはユーザーID、QTH、TLE内容、衛星、予測条件を含めます。QTH・TLE・条件変更で再計算し、通常30分間再利用します。
ローリング表示のため前後1時間を加えて計算し、表示時に現在時刻から24/48時間の範囲へ絞ります。
通過中のPassも含め、LOSに達したPassを除外してAOS順に表示します。夏時間変化でも内部とカウントダウンはUTCです。
計算結果はSQLiteに残るため再起動後も再利用できます。期限切れの結果は次回計算時に削除します。
計算エラーがある結果は60秒で再試行します。異なるポート/プロセスから同時に要求されてもキャッシュ書込みを直列化し、同一条件の重複計算を防ぎます。
現段階ではキャッシュ未作成の別ユーザーも計算の順番を待ちます。大量ユーザー向けのジョブキューは将来の拡張です。

### 確認と公開時の設定

```bat
python -m unittest discover -s tests -v
```

アカウント分離、不正なユーザーID指定、CSRF、ログイン失敗制限、パスワードハッシュ、QTH別の実計算、キャッシュ再利用/期限/TLE変更/再起動を検証します。
これはローカル試作サーバーです。インターネット公開時はHTTPSと本番用WSGIサーバーを用い、SATBOX_COOKIE_SECURE=1を設定してください。
データ保存先はWebから直接取得できない場所に置きます。パスワード再設定、メール確認、スマートフォン通知は今回の範囲に含めません。


## 退会と通過中表示（2026-10-07）

上部メニューの「ログアウト」の左側に「退会」リンクがあります。
退会画面で現在のパスワードを入力し、確認チェックを入れて削除します。
本人の登録情報、QTH、保存済みPass、ログインIDに紐づくログイン失敗記録を削除し、ログアウトします。他ユーザーのデータは削除しません。
削除はPOSTとCSRFトークンで保護され、画面を開くだけでは削除されません。
アカウントごとのランダムなセッション識別子により、退会前のCookieや削除済みIDの再利用で別アカウントにアクセスできないようにしています。
今回の更新後は既存ユーザーも一度ログインし直してください。登録情報とパスワードは引き継ぎます。
旧Passキャッシュは所有者列がないため初回起動時に消去し、必要時に再計算します。

AOS <= 現在時刻 < LOS のPassは通過中として表示します（最低最大仰角条件は引き続き適用）。
衛星名とカウントダウンを赤文字にし、カウントダウンは「LOSまで HH:MM:SS」を表示します。
AOS前はこれまでどおりAOSまでの残り時間です。画面を開いたままでもAOSで赤表示へ切り替わり、LOSで行を非表示にします。
通過中の判定はUTCの時刻差で行い、ブラウザーの毎秒更新で軌道計算を行いません。


## 衛星選択とAOS通知予定（2026-10-07）

上部メニューに「通知設定」「通知予定」を追加しました。
Pass一覧の衛星名に通知ON/OFFのチェックボックスがあります。同じ衛星の複数Passはすべて連動し、操作した時点でユーザーごとの設定を保存します。
個々のPassを選ぶ方式ではありません。その衛星の今後のPass全部について通知条件を適用します。OFFの衛星もPass一覧には表示します。
「通知設定」にはPassが現在一覧にない衛星も含め、web-qth.jsonで利用対象としている衛星の選択欄を用意しています。利用対象の衛星を増やす場合は同ファイルのsatellitesを変更します。
登録済み/新規ユーザーとも初期設定は全衛星OFF、通知最低最大仰角10度、AOS5分前、07:00～24:00です。
通知最低最大仰角は0～90度、AOSの何分前は0～180分（整数）で設定できます。

時刻はユーザーのIANAタイムゾーンのローカル時刻で入力します。
時間帯はAOS時刻ではなく、AOSから指定分数を引いた通知予定時刻で判定します。
開始時刻は含み、終了時刻は含みません。22:00～06:00などの日をまたぐ指定に対応します。
終了は24:00も指定できます。開始と終了が同じ場合は24時間許可します（実機SatBoxと同じ考え方）。
分数の減算と内部保存はUTCで行うため、夏時間が切り替わる日も実時間で指定分前になります。
通知予定時刻を既に過ぎたPassや通過中のPassについて、後追いの通知予定は作りません。

「通知予定」は、本人の通知予定時刻、対象ユーザー、衛星名、AOS、最大仰角、予定（未送信）を表示します。
最低最大仰角はユーザーごとの通知設定を一覧の理由ラベルと通知予定の両方へ適用します。条件未満や通知時間帯外のPassも一覧には理由ラベル付きで残し、通知予定からは除外します。
通知条件変更は保存済みPassから再評価するので軌道を再計算しません。QTH、TLE、予測範囲などが変わった場合は必要なPassを再計算し、通知予定を更新します。
同じPassの通知予定は重複登録しません。OFFにした衛星の予定は削除します。他ユーザーの設定/予定は変更しません。
退会時は通知設定と予定も削除します。既存のアカウント情報は引き継がれます。

この節は通知予定確認段階の説明です。現在のWeb Push送信と定期処理については末尾の「Web PushによるAOS通知」を参照してください。メール送信はありません。
画面を開いたユーザーのキューを必要に応じて生成/更新します。登録ユーザー全員を毎秒計算する処理はありません。
全ユーザー分を手動で一括生成/確認する場合は、サーバーのコマンドラインで次を実行できます（同じ設定ファイルとデータ保存先を使ってください）。

```bat
python plan_notifications.py --all
python plan_notifications.py --login-id ログインID
```

保存先は既存users.sqlite3内のnotification_settings、notification_queue、notification_plan_stateです。
Web画面では他ユーザーのキューを公開しません。上の一括確認コマンドはサーバー管理者のローカル操作用です。
通知予定は現在のTLEを使った予測なので、TLE更新後には予定が変わる場合があります。

モジュールは satbox_notifications/planning.py（Webから独立した時刻/条件判定）、storage.py（設定/予定保存）、satbox_web/notifications.py（画面/保存API）に分離しました。
satbox_web/predictions.pyは共通のPassキャッシュを再利用します。検証済みsatbox_orbitのSGP4計算は変更していません。

実データ確認例：2026-10-07 14:00 Asia/Manilaを基準に、QTH 8.209 / 123.860001 / 20 m、最低MAXEL10度、5分前、07:00～24:00、RS-44/SO-50/ISSをONとしたテスト。
16:09:18 RS-44（AOS16:14:18）
17:26:22 ISS（AOS17:31:22）
18:42:08 SO-50（AOS18:47:08）
テスト用データベースで確認した例です。本番の登録情報は変更していません。



## 通知条件外のPassに理由ラベルを表示（2026-10-07）

最低最大仰角未満、または通知予定時刻が設定時間帯の外となるPassも、一覧から消さず、AOS方位角の右側に設けた「通知状態」列に黄色の「仰角不足」、青色の「時間帯外」ラベルを表示します。両方に該当する場合は両方を表示します。
衛星のチェックボックスは操作できます。通知ON/OFFとは別に、仰角と時間帯の条件で色分けします。
通知予定キューには従来どおり、衛星ON・最低最大仰角・通知時間帯をすべて満たす今後の予定だけを入れます。
文字は通常の濃さで読みやすく表示し、通過中の衛星名とカウントダウンは赤を維持します。LOS到達後の行はこれまでどおり一覧から除外します。
通知予定時刻はAOSから設定分数を引いて求めます。時間帯判定と日跨ぎの扱いはキューと同じです。


## Web PushによるAOS通知（2026-10-07）

スマートフォンのブラウザーから「端末通知」でWeb Pushを登録・解除できます。専用Androidアプリは不要です。
以前の「通知予定のみ・送信なし」は旧段階の説明です。現在は独立した送信プログラムを追加しています。
まだ公開サーバーのHTTPS設置や実端末への配信確認は行っていません。

- `python -m pip install -r requirements-web.txt`
- `python setup_push.py --base-url https://YOUR-HOST/satbox --subject mailto:YOUR-EMAIL`
- HTTPSプロキシの背後で `python serve_web.py --port 8080`
- 事前計算用の別プロセス：`python prepare_notifications.py --loop`
- 送信用の別プロセス：`python send_notifications.py --loop`

公開URL、連絡先を実際の値に置換してください。すべてのプロセスで同じ`--config` / `--data-dir`を使います。
具体的なHTTPS構成例と実機確認手順は `WEB_PUSH設定手順.md` を参照。
既存`web.py`はHTTPローカル試験を継続できますが、スマートフォンへのWeb Push登録はHTTPSが必要です。

`satbox_notifications/push.py`は暗号化端末登録と永続的な配信記録を管理します。送信処理には軌道計算エンジン・Webアプリの依存がありません。
保存済みPassのAOS・最大仰角から通知を作り、通知クリックはユーザー所有の`/pass/<id>`へ移動します。
別ユーザーの登録・詳細は操作/閲覧できず、退会では端末登録・配信記録・Pass詳細も連動削除します。
鍵・暗号化されたSubscription・ユーザーDBは非公開の既存データフォルダーに置きます。ブラウザーの通知先と鍵は画面やログに出しません。
端末登録は最大20台。通知先は対応ブラウザーベンダーのHTTPS Pushサービスに制限します。
ユーザーごとの設定変更はキューを無効化し、OFF衛星・通知条件外の通知は送信しません。
送信側はキューを5秒ごとに確認、予定から120秒以内に再試行し、404/410では無効端末を削除します。
429/5xx/通信障害は最大3回。実際の送信時刻も通知時間帯を確認します。
Pushサービスの受付成功は記録しますが、スマートフォンへの表示完了を保証するものではありません。
受付後・DB記録前にプロセスが落ちると再送の可能性があります。同じPassのtagで表示の重複を抑えます。

仕様参考：[MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)、[pywebpush](https://github.com/web-push-libs/pywebpush)。

## ji1fgx.comへ転送するフォルダーとファイル

次の構成を維持して転送してください。各パッケージの__init__.pyも必要です。

```text
satbox-cloud/
├─ satbox_orbit/          フォルダー全体（__pycache__を除く）
├─ satbox_web/            templates・staticも含む全体（__pycache__を除く）
├─ satbox_notifications/  フォルダー全体（__pycache__を除く）
├─ serve_web.py
├─ web.py
├─ setup_push.py
├─ prepare_notifications.py
├─ send_notifications.py
├─ plan_notifications.py
├─ requirements.txt
├─ requirements-web.txt
├─ web-qth.json
├─ nasa.all
└─ iss-qth.source.json    TLE更新日時の表示用
```

任意でREADME.mdとWEB_PUSH設定手順.mdも転送してください。
backup、tests、__pycache__、比較用JSONは転送不要です。
初回はサーバー側でユーザーを登録し直す場合、ローカルのユーザーDBや秘密鍵の転送は不要です。
ローカルの登録端末は公開URLでは使えないため、公開先のHTTPSページで改めて登録してください。
ユーザーDBや秘密鍵を移行する場合は、HTML公開領域ではなく非公開データ領域に保存します。

HTMLのアップロードだけでは動作しません。Pythonアプリ、事前計算、通知送信を継続実行できるサーバーが必要です。
アプリ本体はWebから直接ダウンロードできない場所に置き、HTTPSリバースプロキシを経由して公開します。

```bash
python -m pip install -r requirements-web.txt
```

サーバー環境に応じたHTTPS・起動方法はWEB_PUSH設定手順.mdを参照してください。

## 更新後にpush.settingsが見つからない場合

通知設定保存後に「Could not build url for endpoint 'push.settings'」となる場合は、Web Push追加前のPythonプロセスが残っている可能性があります。
Pythonのコードは起動時に読み込まれます。ファイルを更新しても、debug=Falseのweb.pyには自動反映されません。
新しいテンプレートと古いプロセスが混在するとこのエラーになります。

1. web.pyを実行したターミナルでCtrl+Cを押して停止します。8080/8081で別々に動かしている場合は両方を停止します。
2. このsatbox-cloudフォルダーで必要ライブラリを導入します。
3. 使用するポートで再起動します。例：python web.py --host 0.0.0.0 --port 8081
4. ブラウザーをCtrl+F5で更新します。

通知設定のPOSTが302なら保存は成功しています。後続の通知予定画面のGETが500となった場合、設定を削除したりDBを作り直したりする必要はありません。


## Xserver共有サーバー対応（2026-10-07）

実環境はCentOS 7、ユーザー導入Python 3.12.3。`python`は2.7なので`.venv`を有効化して使用します。
NumPy 2.4.6はサーバーのGCCではビルドできないため、Xserver用は`requirements-xserver.txt`のNumPy 2.2.6を使用します。
標準`_sqlite3`がないPythonでは`satbox_db.py`が`pysqlite3-binary==0.5.4.post2`へ自動切替します。
**転送一覧にsatbox_db.py、requirements-xserver.txt、deploy/xserver-public/とsatbox_web/cgi_entry.pyを追加してください。**
ローカルのrequirements.txtは変更しません。

アプリ本体は`/home/lily2004/ji1fgx.com/satbox-cloud/`に置きます。
公開入口だけを`public_html/satbox/`へ置きます。`deploy/xserver-public/index.cgi`と同フォルダーの`.htaccess`を使用します。
CGI実行ファイル/設置フォルダーは755、.htaccessは644、CGI改行はLF・BOMなし。
公開URLは`https://ji1fgx.com/satbox/`。URL書換えでログイン/静的ファイル/Service Worker/詳細ページも同じ経路で処理します。
既存public_html直下の.htaccessやweatherは変更しません。
CGI方式は8081の常駐Waitressに接続しません。Web Pushの予定生成と送信は別途定期実行します。
手順全文は`サーバー設置手順.md`。英語版は`Server_Installation_Guide_EN.md`。他社レンタルサーバーの要件、CGI/WSGIの設置方法、公開先変更箇所、通知の定期実行を記載しています。

CGIでNumPy読み込み中に停止する場合の対策: deploy/xserver-public/index.cgiはNumPy/Skyfieldを読み込む前にOPENBLAS_NUM_THREADS・OMP_NUM_THREADS等を1へ設定します。軌道計算に補正は加えません。サーバー上の公開index.cgiにもこの変更を反映してください。


## 通知プログラムのバックグラウンド管理

`notification_workers.sh`をサーバーのsatbox-cloud直下へ転送してください。LF改行・BOMなし。
仮想環境のactivateは不要です。スクリプトが自身のフォルダーの.venv/bin/pythonを直接使用します。

```bash
cd /home/lily2004/ji1fgx.com/satbox-cloud
bash notification_workers.sh start
bash notification_workers.sh status
bash notification_workers.sh stop
bash notification_workers.sh restart
tail -n 20 logs/prepare.log logs/send.log
```

startはnohupで事前計算と送信を起動します。SSH切断後も継続。BLASスレッド数は1に制限。
PIDファイルはlogs/prepare.pid・logs/send.pid、ログは追記で保存。
flockで同時操作を防ぎ、PIDだけでなくLinux /procのスクリプトパスも確認して重複起動/誤停止を防ぎます。
以前のnohupコマンドで起動した相対パスのプロセスも、同じPIDファイルと実行フォルダーで判別します。
手動で前面起動中のプログラムは、初回start前にそれぞれCtrl+Cで停止してください。
SATBOX_DATA_DIRを使っている場合は、CGIと同じ値を環境へ設定して起動します。
このスクリプトはサーバー再起動時の自動起動やOSによる強制終了からの復帰を設定しません。
共有サーバーの常駐運用条件と、Cron等による自動運用は別途確認します。ログ容量も定期確認してください。


Web Push登録診断: 端末通知画面にNotification.permissionの状態（default/denied/granted）と登録の処理段階を表示します。拒否と未確定を区別し、非同期の初期状態確認がボタン操作の結果を上書きしないようにします。更新ファイルはsatbox_web/static/push-settings.jsです。

### 通知音のテスト
通知設定ページの「テスト通知を送る」で、自分の登録済み端末すべてに1回ずつテストWeb Pushを予約します。通知音はスマートフォンの通知設定に従います。通知時間帯・仰角・衛星選択に関係なくテストでき、未保存のフォーム変更は保存しません。1ユーザー1分に1回に制限します。
send_notifications.pyが予約を読み取って送信します。軌道計算・AOS予定には変更を加えません。2分以上古いテストは破棄し、失敗時の再送は行いません。404/410の無効端末は解除します。送信サービスの受付成功は端末の表示・音の保証ではありません。
更新ファイルは satbox_notifications/test_push.py、satbox_web/push.py、satbox_web/templates/notification_settings.html、send_notifications.py です。フォルダー構成を維持し、非公開のsatbox-cloudへ転送してください。更新後は bash notification_workers.sh restart を実行し、通知設定を再読み込みしてください。端末の再登録や鍵の再作成は不要です。

### 3回連続テスト（第1グループのみ）
通知設定のテストボタンは現在、各端末に1/3・2/3・3/3を5秒の待ち時間を挟んで送信します。通知タグは各回別です。10秒後の追加3回はありません。AOS通知は単発のままです。配信遅延・Androidの連続通知抑制により、到着間隔と音の回数は保証されません。途中の送信エラーではその端末の残りを中止します。更新後はnotification_workers.sh restartが必要です。

### AOS通知の送信回数・間隔（通常動作にも適用）
通知設定の「AOS通知の繰り返し」で送信回数1～5回、待ち時間1～15秒を設定し「保存して通知予定を確認」で保存します。通常のAOS通知とテスト通知に共通のユーザー別設定です。初期値3回・7秒。テストボタンもこの回数・間隔を保存しますが、ほかのAOS条件の未保存変更は保存しません。
通常AOS送信は各端末・Passの送信済み回数と次回時刻をDBで管理します。待機sleepで他ユーザーを止めず、成功した各送信の後から指定秒数を待ちます。開始したPassの回数・間隔はその時点の値を使い、途中の変更は次のPassから適用します。端末解除・通知OFFなどでキューから消えたPassは追加送信しません。通知時間外、開始予定から120秒超、AOS後（5秒の猶予あり）は送信しません。AOS直前/0分前設定では全回数を送れない場合があります。旧送信済みPassは再送しません。各回は別タグ。配信時間・実際の鳴動回数は端末側にも依存します。
送信CLIは1秒ごとにDBを確認します。軌道計算は呼び出しません。更新ファイル: satbox_notifications/push.py、satbox_notifications/test_push.py、satbox_web/push.py、satbox_web/notifications.py、satbox_web/templates/notification_settings.html、send_notifications.py。フォルダー構成を維持して非公開satbox-cloudへ転送後、bash notification_workers.sh restartを実行してください。端末再登録や鍵の再作成は不要です。既存DBは必要な列だけ追加して移行します。

### Web画面の音声アナウンス
Pass一覧を開いている間、SatBox-Webと同じspeechSynthesisで日本語アナウンスを行います。有効化の専用ボタンはありません。通知ONの衛星について、設定されたAOS何分前に「RS-44、AOSまで5分。最大仰角47度です。」、AOS時に「サテライト RS-44 ライジング」を各1回読み上げます。LOSは読み上げません。0分前の場合はライジングだけです。事前案内は通知設定時刻、ライジングはAOS時刻で時間帯を判定し、最低最大仰角も適用します。
保存済みPassを画面で判定するだけで、音声処理は軌道を再計算しません。Pushとは独立し、Pushの繰り返し回数は読み上げに適用しません。複数衛星は順に読み上げます。読み上げ中は60秒の一覧自動更新を待ちます。同じタブの再読み込みはsessionStorageで重複抑止（別タブはそれぞれ発声）。古いイベントやタブ休止後の遅れたイベントはまとめて読み上げません。ページ閉鎖・画面ロック・バックグラウンドでは保証できません。
ブラウザーからnot-allowedエラーが返った場合だけ案内を表示し、30秒以内のページクリックで再試行します。日本語音声はHarukaがあれば優先し、それ以外は日本語音声または既定音声です。
更新ファイル: satbox_web/app.py、satbox_web/templates/index.html、satbox_web/static/passes.js、satbox_web/static/announcements.js。非公開satbox-cloudへ構成を維持して転送し、Pass一覧を再読み込みします。Xserver CGIの場合、通知workerの再起動は不要です。ローカルweb.py/serve_web.pyで表示する場合はWebサーバーを再起動してください。

衛星名の音声読みを文字列で指定します。例AO-123→エーオー、ひゃくにじゅうさん。英字と1～4桁の番号を読み仮名へ変換し事前/ライジング両方に適用します。画面表示・Push表示は元の名前を維持します。更新対象satbox_web/static/announcements.js、ブラウザー再読込のみ。

### 事前音声アナウンスの30秒遅延
事前読み上げは設定したPush通知時刻の30秒後です。5分前設定ならPushは5分前、音声は4分30秒前で、残り時間の文言も4分30秒です。AOS時ライジングは遅延しません。表示名を通知端末登録に統一しました。更新後はPass一覧を再読み込み。Xserver CGIは通知workerの再起動不要、ローカル常駐Webは再起動。

### 古いログイン画面からの復帰
CSRFチェックは第三者のサイトからの不正なフォーム送信を防止します。従来の「フォームの有効期限」表示はCSRF不一致を一律に示すもので、画面だけの固定タイマーではありません。ログインセッションの有効期間は従来どおり12時間です。画面復元・別タブのログイン/ログアウト・期限切れ等で古いフォームとセッションが一致しない場合があります。
ログイン前に同一オリジンの/login-tokenから現在のCSRFを取得しPOSTします。期限切れでもブラウザーを閉じずに復帰することを目的としています。不一致POSTでは認証せず、IDを残した新しいログインフォームへ戻します。パスワードは応答に含めません。CSRFを免除していません。通信失敗時は入力したまま再試行できます。Cookieの受け入れが無効、複数Cookieの競合、鍵変更等の場合は別途調査が必要です。
ログイン画面に衛星Pass予測、個別QTH、Web Push、音声案内、初回登録の説明を追加しました。
転送ファイル: satbox_web/auth.py、satbox_web/templates/login.html、satbox_web/static/login.js。非公開satbox-cloudへ構成を維持して転送し、ログイン画面を再読み込みしてください。Xserver CGIは再起動不要。ローカルWebサーバーは再起動。今回の実スマートフォンでの不一致原因は未確定です。

### 衛星選択と管理画面
「衛星選択」はNASA.ALL全体を左、ユーザーの観測対象を右に表示します。>/ <で選択項目、>>/ <<で全件を移動して保存します。10衛星制限はありません。左リストを検索可能、スマートフォンは上下配置です。空の選択も保存可能。多く選ぶほど最初の予測計算は長くなります。既存ユーザーと初回ユーザーはweb-qth.jsonの従来の衛星を初期選択として使用します。
選択はユーザーごとにDB保存し、Pass計算・キャッシュキー・通知設定の衛星候補へ反映します。外した衛星の通知ONとキューは同時に除外します。通知OFFと観測対象削除は別です。TLEに見つからない保存済み衛星は「TLEなし」と表示し、削除可能です。選択変更中の古い予測結果が通知キューを復活させるのを防ぎます。

管理画面は管理者だけに表示・許可されます。登録画面やQTH画面から管理者権限を設定することはできません。登録ユーザー一覧はログインID、コールサイン、QTH、グリッド、タイムゾーン、選択衛星数、登録端末数、権限を表示します。パスワードハッシュ・セッショントークン・Pushの鍵やエンドポイントは表示しません。ユーザー編集・削除機能は追加していません。
サーバーのsatbox-cloudで次を実行し、既存のログインIDに管理者権限を付与します（ji1fgxは対象ログインIDに置き換え可能）。
```
.venv/bin/python manage_admin.py grant ji1fgx
```
解除は revoke を使用します。カスタム--config/--data-dirを使っている場合はこのコマンドにも同じ引数を付けます。管理者に指定したユーザーはページを再読み込みするとナビに「管理画面」が表示されます。ほかのユーザーはURLを直接開いても403です。

管理画面の「NASA.ALLを更新」は https://www.amsat.org/tle/current/nasa.all の固定HTTPS配信元から取得し、容量上限・名前の重複・TLEペア・SGP4モデルを検証した後に原子的に置き換えます。同時更新はファイルロックで防ぎます。変更前のTLEと更新メタデータはprivate folder内tle-backups/に保存します。取得失敗や不正TLEは旧TLEを維持します。全ユーザーの古い通知キューを無効にし、新しいTLEハッシュでキャッシュを再生成します。管理画面の更新日時はUTC、Pass一覧はユーザーのタイムゾーンです。NASA.ALLの更新はこの管理機能から行ってください。
prepare_notifications.pyは5秒ごとにファイルの変更とユーザーのQTH/衛星選択の変更を確認し、変更時または15分経過時だけキャッシュを使って予測・キュー生成します。送信プログラムで軌道計算を行いません。更新直後にPass一覧を開いても新データを計算できます。多数の衛星・ユーザーでのXserverの処理時間は別途確認してください。

更新ZIPのsatbox_web/、satbox_notifications/、prepare_notifications.py、manage_admin.py、README.mdを非公開satbox-cloudへ、構成を維持して転送してください。NASA.ALLやユーザーDB・鍵の上書きは含めません。転送後は bash notification_workers.sh restart を実行し、上の管理者付与コマンドを実行してページを再読み込みします。DBの追加列・テーブルは自動移行します。通知端末の再登録は不要です。ローカル常駐WebはWebサーバーも再起動します。日英対応と地図表示は今回の更新には含めません。


### 初期管理者と権限変更
特定のログインIDを管理者として組み込んでいません。ユーザー登録は常に一般権限です。
公開時は管理者用アカウントを通常の登録画面から作成し、サーバーのシェルで一度だけ実行します。
```bash
cd /home/lily2004/ji1fgx.com/satbox-cloud
.venv/bin/python setup_admin.py YOUR_LOGIN_ID
```
既に管理者が存在する場合は初期設定を拒否します。setup_admin.pyは非公開のsatbox-cloud内に置いてください。
以後は管理画面のユーザー一覧から管理者の昇格・解除が可能です。最後の管理者の解除・退会は拒否します。
復旧やサーバー上での手動管理にはmanage_admin.py grant/revokeを使用できます。
既存の管理者設定は維持されます。初期設定を再実行する必要はありません。

[Web Pushの設定・端末登録・テスト手順](WEB_PUSH設定手順.md)

## 著作権・お問い合わせ

Copyright © 2026 Kouichi Ueno — JI1FGX/DU9

お問い合わせ先：[du9@ji1fgx.com](mailto:du9@ji1fgx.com)

## SatBox Cloudの紹介・操作説明

- 日本語：[https://ji1fgx.com/261008.html](https://ji1fgx.com/261008.html)
- 英語版：[https://ji1fgx.com/en/261008.html](https://ji1fgx.com/en/261008.html)
