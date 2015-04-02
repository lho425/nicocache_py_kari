proxy_port = 8080;

function FindProxyForURL(url, host){
    if(shExpMatch(host, "*nicovideo.jp") &&
       url.startsWith("http:")){ // https等を弾く
        return "PROXY 127.0.0.1:" + proxy_port;
    }

    return "DIRECT";
}
