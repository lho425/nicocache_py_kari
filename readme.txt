#不安定版nicocache.py
これは、ニコニコ動画の動画をキャッシュしたりするソフトです。
nicocache_nlの代わりを目指して作られています。

まだ作りかけです。一応動きますが、機能は少ないので、nicocache_nlを使ったほうが良いでしょう。
コードを読んでアドバイスをくれたり、協力してくれる人を求めています

python2.7が必要です。
https://www.python.org/downloads/ にあります。
windowsの人は "C:\Python27" にpythonをインストールしてください。
それが嫌な人は、適宜NicoCache_Py.batを書き換えてください。

ログの出力はutf-8ですが、
NicoCache_Py.batを使うと、nkfを利用して文字コードをsjisに変換してからコンソールに出力します。
将来的にはnicocache.py側でなんとかします。というかpython3でも動くようにします。python使いの方ごめんなさい。

私はcygwin上でしか動かさないので、現段階ではwindowsのサポートはあまりできません。

引数に debug という文字を渡すと詳細なログを出力します。

config.pyを編集すると、設定が変えられます。
詳しくはconfig.pyの上の方に書いてあることを読んでください。

ライセンスはGPLv3です。


#コマンドAPI
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

#以下開発者向け

nicocache.pyにあるクラス等の内部のAPIは全く安定してません。
おそらく、これから大きく書き換わることでしょう。(内部アーキテクチャの設計し直しを予定)


ニコニコに関係ない部分はproxthetaディレクトリに分離されています。
これは、透過的プロクシを実装するための、低水準ライブラリ/フレームワークです。
よくあるオブジェクト指向ベースのwebフレームワークとは違い、なるべく関数型プログラミングチックになっています。
proxthetaのAPIは大きく変わる予定はありませんが、気が変わるかもしれません。
proxthetaのライセンスはWTFPLv2です。好き勝手流用して構いません(自己責任で)。

nicocache.pyの内部はこれからさらに抽象化とモジュール化が行われ、汎用的なモジュールはWTFPLでライセンスされることになるでしょう。
そうなるとGPLの部分は最終的にはなくなるかもしれません。

作った人: LHO425 (【ニコニコ】自動ローカル保存プロクシ NicoCache19 スレの142)
