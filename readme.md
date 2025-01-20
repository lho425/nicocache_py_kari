# NicoCache_Py(仮)

## ⚠️このリポジトリはArchiveされています。⚠️ / This repo is arrchived.

以下の理由で、このリポジトリはArchiveされました:

- 一般会員でも自由にシークできるようになってキャッシュする意味が自分にとってあまりなくなった。
- 一般会員でもかなりいい画質で見れるようになってキャッシュする意味が自分にとって全くなくなった。
- 暗号化HSLに対応するのはとても面倒だし、ニコニコの回線は特に遅くは感じないのでキャッシュする必要がない。
- 今のご時世SSLの独自ルート証明書の登録も大変。
- 自分でも使ってない。
- 動画を保存したいならyt-dlpでも使えば良い。


## これは何？

これは、ニコニコ動画の動画をキャッシュしたりするソフトです。
nicocache_nlの代わりを目指して作られています。

まだ作りかけです。一応動きますが、機能は少ないので、nicocache_nlを使ったほうが良いでしょう。
コードを読んでアドバイスをくれたり、協力してくれる人を求めています。

ライセンスはGPLv3です。

### なぜNicoCache_nl+modの再発明が必要？

そもそもそんな必要はないです。
 - 自分用に汎用的に使えるプロクシサーバが欲しかったのでついでに作った
 - ARM版のjavaランタイムをoracleがプロプライエタリにしてしかも再配布禁止にしてるのがムカついた
 - そのおかげでせっかく苦労しておうちのNASにjava入れたのにまともに動いてくれなかった
 - 本家nlのソースコードがデカすぎて追い切れなかった
そんなんで、じゃあどうせなら自分用にNicoCacheモドキつくるかーと思って作ったのを公開しただけです。こんなものを無理して使う必要など全くないのです！
もちろん使ってくれてバグ報告とかしていただければ嬉しいですが。

## 準備: NicoCache_Py(仮)を動かすのに必要なもの

### unix系
bash と git と Cコンパイラが必要です。git と Cコンパイラはなくても構いませんが、その場合aptやbrewでpython2.7+pip2を自分でインストールしてください。
#### python環境の用意
git と Cコンパイラがある場合は`./setup_python.sh`を実行してください。
git と Cコンパイラがない場合もしくは`./setup_python.sh`が失敗した場合はaptやbrewでpython2.7+pip2を自分でインストールしてください。

ubuntu系なら
```sh
sudo apt install python
sudo apt install python-pip
pip install --upgrade pip
```
みたいにやってください。

#### 依存するライブラリの用意
`./setup_dependency.sh`を実行してください。

以降、NicoCache_Py.sh を実行すると NicoCache_Py(仮) が動作します。

### windows
#### python環境の用意
python2.7が必要です。
https://www.python.org/downloads/ にあります。
windowsの人は "C:\Python27" にpythonをインストールしてください。
それが嫌な人は、適宜`*.bat`を書き換えてください。

#### 依存するライブラリの用意
`./setup_dependency.bat`を実行してください。

以降、NicoCache_Py.bat を実行すると NicoCache_Py(仮) が動作します。


## 設定

初回起動時に生成されるconfig.confを編集すると、設定が変えられます。
詳しくはconfig.confに書いてあることを読んでください。

## https 通信のプロクシのためのセットアップ (unix系のみ対応)
./gen-ssl-mitm-keys.sh を実行し、作成されたssl証明書 mitm/server.crt をあなたのOSにインストールします。

windowsも対応予定。

## コマンドAPI
    http://www.nicovideo.jp/watch/smXXXX/save
にアクセスすると、cache直下にあるsmXXXXのキャッシュ動画ファイルがcache/saveに移動され、ファイル名にタイトルと拡張子がつきます。

    http://www.nicovideo.jp/watch/smXXXX/unsave
にアクセスすると、cache/saveにあるsmXXXXのキャッシュにsaveコマンドと逆の操作が行われます。

    http://www.nicovideo.jp/watch/smXXXX/rename
にアクセスすると、cache直下にあるsmXXXXのキャッシュ動画ファイルが削除されます。


次のブックマークレットを使うとsaveコマンドを1クリックで実行できます。
ブラウザでhttp://www.nicovideo.jp/watch/smXXXXを開いている時に仕様してください。
javascript: $.get(location.href + "/save", function(data){alert(data)})

コマンドAPIは動画をキャッシュしている最中でも使えます。
windowsは使用中のファイルに対する操作が行えないので、キャッシュsuspend時、もしくはcomplete時に操作が実行されます。

なので、removeコマンドを実行したキャッシュをsaveできてしまったりします(実際はそう見えるだけ)。



## ログ

引数に debug という文字を渡すと詳細なログを出力します。

http://localhost:8080/log.txtにアクセスすると(ポート8080でlistenしてるとき)、ログが見れます。

log.txtにコンソールに表示されるのと同じログが残ります。古いlog.txtはlog.old.txtにリネームされます。

log.txtが1GBを超えるとlog.txt.1という名前に変更され、新しくlog.txtができます。log.txt.1は次回起動時に削除されます。


## 以下開発者向け
初版から内部アーキテクチャが二転三転しながら、なんとか今のアーキテクチャに落ち着きました。自分が考える上で一番マシな設計になったと思います。

ニコニコに関係ない部分はnicocache/proxthetaディレクトリに分離されています。
これは、プロクシサーバを実装するための、自作の低水準ライブラリ/フレームワークです。
よくあるオブジェクト指向ベースのwebフレームワークとは違い、なるべく関数型プログラミングチックになっています。

proxthetaのAPIは大きく変わる予定はありませんが、python3に移植するときにhttpmesモジュールのAPIを少し修正する予定です。
proxthetaのライセンスはWTFPLv2です。好き勝手流用して構いません(無保証ですが)。


作った人: LHO425 (【ニコニコ】自動ローカル保存プロクシ NicoCache19 スレの142)
