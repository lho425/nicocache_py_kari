#現段階での挙動

 - 完全な非エコノミーキャッシュがある場合それを使うようになる
 - 消された動画、有料動画で、エコノミーな完全なキャッシュしかないときは、それを送るようになっている
 - 上の挙動は課金やプレミアムと相性が悪いかもしれない

#cacheフォルダ以下にあるファイルの一覧をキャッシュする機能

高速化のため、起動時にキャッシュの一覧をメモリ上に構築します。

ファイルやフォルダの追加、削除、リネームを行うとそれを認識してキャッシュ一覧を再構築します。

また、ファイルのリネーム等を認識するのは動画のリクエストやコマンドを実行するときです。リネームした瞬間ではないです。

ディレクトリの更新日時を利用するので、OSによってはうまく動かないかも知れません。

windowsでは、キャッシュフォルダ、またはサブフォルダにシンボリックリンクを使用している場合、ファイルのリネーム等を認識出来ません。エラーが起きます。その場合nicocacheを再起動してください。

デリケートな機能なので、その他にも不具合があるかもしれません。

#重要な問題

## (cygwinでなくて)windowsでchromeを使っていると、スリーブからの復帰時に暫く通信が固まってしまう。

対処法1: 同梱しているproxy_sample.pacのnicocache_portを書き換えた上で、proxy_sample.pacを使うようにwindowsを設定する。
(git 使ってる人はproxy_sample.pacをproxy.pacにコピーしてから書き換えたほうが良いでしょう。)

対処法2: 同梱しているextensions/disable/procpool_getaddrinfo.pyをextensions直下に移す。
procpool_getaddrinfoエクステンションにより、固まってしまう部分をマルチプロセスで並列に処理します。

なぜか、windows版のpythonだと、hostの名前解決の関数が、他のスレッドをブロックしてしまうのが原因。

chromeでしか起きないのは、chromeがスリープ復帰時等にでたらめなhost名にアクセスするから。

存在しないhost名を名前解決しようとすると、とても時間がかかる。なので、上の要員が合わさって問題が起きる。


# その他

現状面倒臭がってほとんどスレッドのロックを行っていません。
同時アクセス等で、どこかでエラーが起きるかもしれません。
pythonはビルトイン関数はアトミックに実行されるのが保証されているので、大丈夫とは思いますが。
