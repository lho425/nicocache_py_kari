// ==UserScript==
// @name nico-thumb-popup
// @include http://www.nicovideo.jp/*
// @include https://www.nicovideo.jp/*
// ==/UserScript==

// 著者: 【ニコニコ】自動ローカル保存プロクシ NicoCache20 >>32氏 (http://anago.open2ch.net/test/read.cgi/software/1426235895/32)
// ライセンス: パブリックドメイン(open2chへの投稿であったことに由来)

// 著者: LHO425
// ライセンス: WTFPLv2


/*
 * 基本的に、動画へのリンクにマウスが乗ったらpopupを表示し、
 * リンクから外れたらpopupを消す、ということを行う。
 * しかし、jsのDOMにより以下のようなこと
 *   - リンクにマウスが乗っているときにリンク要素が突然消える
 *   - マウスが乗っているリンクが、突然別のリンクに変わる
 * ということを考慮しなくてはいけない。
 */

window.nicoThumb = {};
window.nicoThumb.debug = false;

function logger_debug() {
	if (window.nicoThumb.debug) {
		console.log.apply(console, arguments);
	}
}

/***************** マウスオーバーを検知しポップアップを発動する部分 **********/
(function () {
	var nicoURLPattern = new RegExp("//(?!blog)(?:[^.]+.nicovideo.jp/(?:.*?%2F)?(watch|gate|community(?=/co)|mylist|user|channel(?=/ch)|seiga)|nico.ms)(?:/|%2F)((?=[1-9]|sm|nm|so|lv|co|ch|im|sg|mg)[a-z0-9]{2}[0-9]+)");
	document.body.addEventListener("mouseover", function (event) {
		var target = event.target;
		while (!/^(A|BODY)$/.test(target.tagName)) target = target.parentNode;
		nicoURLMatch = nicoURLPattern.exec(target.href);
		if (target.tagName === "A" && nicoURLMatch) {
			if (!target.onmouseover) {
				var contentType = (nicoURLMatch[1] || "watch");
				var contentID = nicoURLMatch[2];
				popThumbOn(contentType, contentID, event);
				// 一度popupしたリンク要素はイベント登録。
				target.onmouseover = function (event) {
					popThumbOn(contentType, contentID, event);
				};
				target.onmouseout = function () {
					// これがないと動画を移動した時に右上の投稿者のポップアップが前の投稿者のままになってしまう
					target.onmouseover = null;

					popThumbOff();
				};
			}
		} else {
			popThumbOff();
		}
	});
})();


/***************** 実際にポップアップしてマウス追従したりするDOM部分 **********/

(function () {
	var popupThumbWidth = 312;
	var popupThumbHeight = 176;
	var nicoThumb = document.createElement("div");
	nicoThumb.id = "nicoThumb";
	document.body.appendChild(nicoThumb);
	//nicoThumb.style.display = "none"
	var nicoThumbTable = {};// {"watch/sm12345": thumbIframe;} を格納する
	// thumbIframeはサムネイルIFrameのelement
	// なぜこんなテーブルをつくるか？それは、getElementsBy云々を呼んでいちいち走査するよりもパソコンに負荷がかからないだろうという予想から。
	// まあ、あんまり変わんないかも

	var currentPopupThumb = null;
	var currentMouseMoveEventListener = null;


	function drawPopupThumb(drawPopupOnRight, topIntercept, event) {


		var left;

		//カーソルがマウスオーバーした時点で、カーソル真ん中より左にあったときは、右にポップアップを表示するフラグが立っている
		if (drawPopupOnRight) {
			left = window.scrollX + event.clientX + 20;
		} else {
			left = window.scrollX + event.clientX - 20 - popupThumbWidth;
		}
		currentPopupThumb.style.left = left + "px";

		var top = ((window.scrollY + event.clientY) - 20 - popupThumbHeight) + topIntercept;

		currentPopupThumb.style.top = top + "px";
		logger_debug("### drawPopupThumb dubug log ###");
		logger_debug("window.scrollY", window.scrollY);
		logger_debug("event.clientY", event.clientY);
		logger_debug("drawPopupOnRight", drawPopupOnRight);
		logger_debug("left", left);
		logger_debug("topIntercept", topIntercept);
		logger_debug("top", top);

	}

	function getThumbIframe(contentType, contentID) {
		var path = contentType + "/" + contentID;
		var thumbIframe = null;
		for (var aPath in nicoThumbTable) {
			if (path === aPath) {
				thumbIframe = nicoThumbTable[path];
				break;
			}
		}

		if (thumbIframe === null) {
			thumbIframe = document.createElement("iframe");
			thumbIframe.style.display = "none";
			//ココらへんはcssでやるべきだけど、なんか上手くいかないので、ニコ動公式のiframe埋め込みの通りに属性を設定してやる
			thumbIframe.width = popupThumbWidth;
			thumbIframe.height = popupThumbHeight;
			thumbIframe.scrolling = "no";
			thumbIframe.frameborder = "0";
			thumbIframe.style.zIndex = 1000000;
			thumbIframe.style.position = "absolute";

			var host = "ext.nicovideo.jp";
			var thumbIframePath;
			if (contentType == "watch") {
				if (contentID.startsWith("lv")) {
					host = "live.nicovideo.jp";
					thumbIframePath = "embed/" + contentID;
				} else {
					thumbIframePath = "thumb/" + contentID;
				}
			} else if (/^(mylist|user|community|channel)$/.test(contentType)) {
				thumbIframePath = "thumb_" + contentType + "/" + contentID;
			} else if (contentType == "seiga") {
				host = "ext.seiga.nicovideo.jp";
				thumbIframePath = "thumb/" + contentID;
			} else {
				console.log("nico-thumb-popup: unknown content:", contentType + "/" + contentID);
				thumbIframePath = "thumb/" + contentID;
			}
			// protocol is "http:" or "https:"
			protocol = window.location.protocol
			thumbIframe.src = protocol + "//" + host + "/" + thumbIframePath;
			nicoThumb.appendChild(thumbIframe);
			nicoThumbTable[path] = thumbIframe;
		}
		return thumbIframe;
	}

	window.popThumbOn = function (contentType, contentID, event) {
		var thumbIframe = getThumbIframe(contentType, contentID);
		if (currentPopupThumb !== thumbIframe) {
			popThumbOff();
		}
		currentPopupThumb = thumbIframe;
		currentPopupThumb.style.display = "";

		var drawPopupOnRight;
		//カーソルが真ん中より左にあるときは、右にポップアップを表示する
		//マウスオーバーした時点で決める
		if (event.clientX < window.innerWidth / 2) {
			drawPopupOnRight = true;
		} else {
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
		if (extra > 0) {
			//上にはみ出ていたら、はみ出ている分+αを下にずらす、つまりtop座標を増やす
			topIntercept = extra + 45;
		}

		logger_debug("### popThumbOn dubug log ###");
		logger_debug("event.clientY", event.clientY);
		logger_debug("popupThumbHeight", popupThumbHeight);
		logger_debug("-(event.clientY - popupThumbHeight - 30)", extra);
		logger_debug("-(event.clientY - popupThumbHeight - 30) > 0", extra > 0);
		logger_debug("topIntercept", topIntercept);

		currentMouseMoveEventListener = function (event) {
			drawPopupThumb(drawPopupOnRight, topIntercept, event);
		};
		document.addEventListener("mousemove", currentMouseMoveEventListener, false);
	};

	window.popThumbOff = function () {
		if (currentPopupThumb !== null) {
			currentPopupThumb.style.display = "none";
			document.removeEventListener("mousemove", currentMouseMoveEventListener, false);
		}
	}
})();
