nicocache_port = 8080; //listenPortと同じ値に書き換えてください。
nicocache_host = "127.0.0.1"; //NAS等で動かす人はここも書き換えてください


/*---------------------------------------*/
proxy_str = "PROXY " + nicocache_host + ":" + nicocache_port;

function FindProxyForURL(url, host){
    if(shExpMatch(host, "*nicovideo.jp")) {
        return proxy_str;
    }

    return "DIRECT";
}
