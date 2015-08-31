# これは何?

cache/save フォルダ(nicocacheのデフォルト設定の場合)に、キャッシュ途中の動画やエコノミーの動画があった場合、夜中の２時くらいに非エコノミーの完全なキャッシュにします。

本家nicocache_nlのmovieFetcherのような機能を提供します。


# 使い方

ニコニコ動画にログインするので、メールアドレスとパスワードが必要です。
どこかに(たとえば、C:\Users\Hoge\nicouser.txt)ニコニコ動画に登録したメールアドレスとパスワードを書かなくては行けません。
これをpasswordFileを呼ぶことにします。

passwordFileは
一行目にメールアドレス
二行目にパスワード
を書かなくては行けません。安全でないので、アクセス権を適切に設定することをおすすめします。

passwordFileを作ったら、config.confに以下の二行を追記します。

[nicodwarf]
passwordFile=C:\Users\Hoge\nicouser.txt


C:\Users\Hoge\nicouser.txtは適宜読み替えてください(passwordFile=にはpasswordFileのパスを設定してください。unix形式のパスももちろん可能です)。

passwordFileは相対パスでも構いません。その場合、NicoCache_Py.batやNicoCache_Py.shがある場所が基点となるはずです(今後どうなるかは不明)。


# License

WTFPLv2 (license.txtに従います)

無保証です。


# 作者

python版nicocacheを作った人

詳しいことはpython版nicocacheのreadmeを参照してください。
