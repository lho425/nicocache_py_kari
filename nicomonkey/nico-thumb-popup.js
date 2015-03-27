// ==UserScript==
// @name nico-thumb-popup
// @include http://www.nicovideo.jp/*
// ==/UserScript==

//バグがあるかもしれません
//ブラウザが暴走するかもしれません
//ソースコードがあまり綺麗でない
//コメントも少ない

var undefined;

console.log("nico-thumb-popup");

window.nicoThumb = {};
window.nicoThumb.debug = false;

function logger_debug(){
    if (window.nicoThumb.debug){
	console.log.apply(console, arguments);
    }
}

var watchIdPattern = new RegExp(".*/watch/(..[\\d]+).*");


var popupThumbWidth = 330;
var popupThumbHeight = 196;
var nicoThumb = document.createElement("div");
nicoThumb.id = "nicoThumb";
document.body.appendChild(nicoThumb);
//nicoThumb.style.display = "none"
var nicoThumbTable = {};// {"sm12345": thumbIframe;} を格納する
// なぜこんなテーブルをつくるか？それは、getElementsBy云々を呼んでいちいち走査するよりもパソコンに負荷がかからないだろうという予想。
// まあ、あんまり変わんないかも

currentPopupThumb = null;

// <a href="watch/sm1234" ...部分をポップアップするように書き換える
function rewriteVideoLinkTagToPopup(getVideoLinkTags, getWatchIdFromVideoLinkTag){
    var videoLinkTags = getVideoLinkTags();
    var i;
    
    for (i=0; i<videoLinkTags.length; i++){
	(function(){
	    var videoLinkTag = videoLinkTags[i];

	    videoLinkTag.addEventListener("mouseover", function(event){
		popThumbOn(getWatchIdFromVideoLinkTag(videoLinkTag), event);
	    }, false);
	    videoLinkTag.setAttribute("onMouseOut", "return popThumbOff()");
	})();
    }
}


(function(){

    function rewriteVideoLinkTagInWatchDescription(){

	return rewriteVideoLinkTagToPopup(
	    function(){
		return document.getElementsByClassName("watch"); 
	    },
	    function(videoLinkTag){
		return videoLinkTag.textContent;
	    });
    }

    var videoDescription = document.querySelector('p.videoDescription.description');
    if (! videoDescription){
	return;
    }

    rewriteVideoLinkTagInWatchDescription();

    var mo = new MutationObserver(function(mutationRecords){
	{
            mutationRecords.forEach(function(mutation) {
		rewriteVideoLinkTagInWatchDescription()
	    });
	    
	}
    });
    mo.observe(videoDescription, {childList:true});
})();

/************* videoExplorer部分の書き換え ***************/
(function(){
    function rewriteVideoLinkTagInVideoExplorer(){

	return rewriteVideoLinkTagToPopup(
	    function(){
		return document.querySelectorAll(".column4>a.link, .column1 a.link.title");
	    },
	    function(videoLinkTag){
		return videoLinkTag.href.match(watchIdPattern)[1];
	    });
    }

    var videoExplorerContent = document.querySelector('.videoExplorerContent');
    if (! videoExplorerContent){
	return;
    }

    rewriteVideoLinkTagInVideoExplorer();
    
    var mo = new MutationObserver(function(mutationRecords){
	{
            mutationRecords.forEach(function(mutation) {
		if (mutation.target.getAttribute("class").startsWith("searchContent")){
		    rewriteVideoLinkTagInVideoExplorer();
		}
	    });
	    
	}
    });
    mo.observe(videoExplorerContent, {childList:true, subtree :true});
})();

/************* videoExplorer以外の通常のリンクの書き換え ******************/
function rewriteVideoLinkInNormalPage(){

	return rewriteVideoLinkTagToPopup(
	    function(){
		var returnLinkTags = [];
		var linkTags = document.getElementsByTagName("a");
		var i;
		for (i=0; i<linkTags.length; i++){
		    var linkTag = linkTags[i];
		    var href = linkTag.href;
		    if ( href.startsWith("/watch") ||
			   href.startsWith("http://www.nicovideo.jp/watch")){
			
			returnLinkTags.push(linkTag);
		    }
		}

		return returnLinkTags;
	    },
	    function(videoLinkTag){
		return videoLinkTag.href.match(watchIdPattern)[1];
	    });
    }
rewriteVideoLinkInNormalPage();

/***************** 実際にポップアップしてマウス追従したりするDOM部分 **********/
function drawPopupThumb(drawPopupOnRight, topIntercept, event){

    
    var left;

    //カーソルがマウスオーバーした時点で、カーソル真ん中より左にあったときは、右にポップアップを表示するフラグが立っている
    if (drawPopupOnRight){
	left = window.scrollX + event.clientX + 30;
    } else {
	left = window.scrollX + event.clientX- 30 - popupThumbWidth;
    }
    currentPopupThumb.style.left = left + "px";

    var top = ((window.scrollY + event.clientY) - 30 - popupThumbHeight) + topIntercept;
    
    currentPopupThumb.style.top = top + "px";
    logger_debug("### drawPopupThumb dubug log ###");
    logger_debug("window.scrollY", window.scrollY);
    logger_debug("event.clientY", event.clientY);
    logger_debug("drawPopupOnRight", drawPopupOnRight);
    logger_debug("left" ,left);
    logger_debug("topIntercept", topIntercept);
    logger_debug("top", top);
    
}

popThumbOn = function (watchId, event){
    var thumbIframe = null;
    for(var aWatchId in nicoThumbTable) {
	if (watchId === aWatchId){
	    thumbIframe = nicoThumbTable[watchId];
	    break;
	}
    }

    if (thumbIframe === null){
	thumbIframe = document.createElement("iframe");
	thumbIframe.style.display = "none";
	thumbIframe.style.width = popupThumbWidth + "px";
	thumbIframe.style.height = popupThumbHeight +"px";
	thumbIframe.style.zIndex = 10000;
	thumbIframe.style.position = "absolute";
	thumbIframe.src = "http://ext.nicovideo.jp/thumb/" + watchId;

	nicoThumb.appendChild(thumbIframe);
	nicoThumbTable[watchId] = thumbIframe;	
    }


    currentPopupThumb = thumbIframe;
    currentPopupThumb.style.display = "";

    var drawPopupOnRight;
    //カーソルが真ん中より左にあるときは、右にポップアップを表示する
    //マウスオーバーした時点で決める
    if (event.clientX < window.innerWidth/2){
	drawPopupOnRight = true;
    }else{
	drawPopupOnRight = false;
    }

    // =======================ページの一番上==
    //    A
    //  window.scrollY              ---------popupのtop--
    //    V                                  |はみ出た分           |
    // --------ブラウザで表示してる一番上端-------|--                 |


    var topIntercept = 0; // topの切片
    //上にはみ出ていたら、はみ出ている分+αを下にずらす、つまりy座標を増やす
    //下にずらす分はマウスオーバーした時点で決める
    //ポップアップのtop座標 = (カーソルのページの一番上からの距離) - (カーソルより上にポップアップして欲しいので、上にずらす分) - (カーソルから少し離す分)
    //=(window.scrollY + event.clientY) - popupThumbHeight - 30
    //はみ出た分 = window.scrollY - top  = - (event.clientY - popupThumbHeight - 30)
    var extra = -(event.clientY - popupThumbHeight - 30);
    if ( extra > 0){
	//上にはみ出ていたら、はみ出ている分+αを下にずらす、つまりtop座標を増やす
	topIntercept = extra + 45;
    }

    logger_debug("### popThumbOn dubug log ###");
    logger_debug("event.clientY", event.clientY);
    logger_debug("popupThumbHeight", popupThumbHeight);
    logger_debug("-(event.clientY - popupThumbHeight - 30)", extra);
    logger_debug("-(event.clientY - popupThumbHeight - 30) > 0", extra > 0);
    logger_debug("topIntercept", topIntercept);


    // todo!!! この実装だとイベントが1つしか登録できなくて、他のイベントが登録できないので、addEventListennerを使うように変更
    document.onmousemove = function(event){
	drawPopupThumb(drawPopupOnRight, topIntercept, event);
    }
};

popThumbOff = function() {
    currentPopupThumb.style.display = "none";
     document.onmousemove = null;// todo!!! event
};
