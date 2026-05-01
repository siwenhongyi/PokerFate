-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','code','tip','zh','tw','en','jp','ko',}
    local bodys = {
{"RET_OK",0,nil,nil,nil,nil,nil,nil},
{"ERR_SERVER_STOP",100,nil,"服务器停服","伺服器維護中","Server under maintenance","サーバーメンテナンス中","서버 점검 중입니다"},
{"ERR_INNER_ERROR",101,nil,"服务器内部错误","伺服器內部異常","Internal server error","サーバー内部エラー","서버 내부 오류입니다"},
{"ERR_NOT_ENOUGH_MONEY",102,nil,"金币不足","籌碼不足","Insufficient chips","チップが足りません","칩이 부족합니다"},
{"ERR_GM_KICK",103,nil,"账号已被强制登出","帳號已被強制登出","Your account has been forcibly logged out","アカウントが強制ログアウトされました","운영자에 의해 강제 접속 종료되었습니다"},
{"ERR_OTHER_KICK",104,nil,"您已经在其他地方登录。","您已在其他裝置登入。","Your account is logged in on another device","他の端末でログインされました","您已經在其他地方登錄。"},
{"ERR_SERVER_BUSY",105,nil,"服务器繁忙","伺服器繁忙","Server busy","サーバーが混雑しています","서버가 혼잡합니다"},
{"ERR_MSG_FREQUENT",106,nil,"操作太频繁,稍后再试","操作過於頻繁，請稍後再試","Too many requests. Please try again later","操作が頻繁すぎます。しばらくしてからお試しください","요청이 너무 빈번합니다. 잠시 후 다시 시도하세요"},
{"ERR_INVALID_PARAM",107,nil,"无效参数","無效參數","Invalid parameters","無効なパラメータです","잘못된 매개변수입니다"},
{"ERR_NOT_SIT",108,nil,"没有坐下","未入座","Not seated","着席していません","착석하지 않았습니다"},
{"ERR_NOT_IN_GAME",109,nil,"没有在游戏中","不在遊戲中","Not in a game","ゲーム中ではありません","게임 중이 아닙니다"},
{"ERR_NO_MORE_DATA",110,0,"没有数据","沒有數據","No data available","データが存在しません","데이터가 없습니다"},
{"ERR_LEVEL_NOT_REACH",111,nil,"等级不够","等級不足","Level too low","レベルが足りません","레벨이 부족합니다"},
{"ERR_EXCEED_BET_LIMIT",112,nil,"超下注上限","下注額超出上限","Bet exceeds the limit","ベット額が上限を超えています","베팅 가능 금액 최대치를 초과했습니다"},
{"ERR_BUST_PROTECT_NO_LEFT_TIMES",113,nil,"破产保护条件不满足,没有剩余次数","破產保護次數已用盡","Bankruptcy protection limit reached","破産保護の回数を使い果たしました","파산 보호 조건을 만족하지 않습니다. 남은 횟수가 없습니다"},
{"ERR_BUST_PROTECT_TOO_MUCH_COIN",114,0,"破产保护条件不满足,拥有的金币过多","籌碼充足，無法觸發破產保護","You have enough chips, bankruptcy protection not available","チップが十分あるため、破産保護を使用できません。","파산 보호 조건을 만족하지 않습니다. 보유 칩이 너무 많습니다"},
{"ERR_ACTIVITY_NOT_OPEN",115,nil,"活动未开启","活動未開啟","Event has not started","イベントは開始していません","이벤트가 시작되지 않았습니다"},
{"ERR_NOT_IN_YOUR_TURN",116,0,"行动失败，不是你的回合","未到行動回合","Not your turn","ターンではありません","행동할 수 없습니다. 당신의 턴이 아닙니다."},
{"ERR_MAINTAIN_SOON_FORBID_GAME",117,nil,"即将停服，禁止创建与进入房间","即將停服，禁止創建或進入房間","Maintenance starting soon. Creating or entering tables is disabled","間もなくサーバーが停止するため、ルームに入ったり新しく作ったりできません","Maintenance starting soon. Creating or entering tables is disabled"},
{"ERR_INVALID_REQUEST",118,0,"无效请求","無效的請求","Invalid request","無効なリクエストです",nil},
{"ERR_NO_CHIPS_FORBID_SWITCH_ROOM",119,nil,"切换牌桌失败，当前筹码不足房间最小买入","切换牌桌失败，当前筹码不足房间最小买入","切换牌桌失败，当前筹码不足房间最小买入","切换牌桌失败，当前筹码不足房间最小买入","切换牌桌失败，当前筹码不足房间最小买入"},
{"LOGIN_ERR_KEY_ERR",1001,nil,"登录失败,key错误","Key錯誤，登入失敗","Key error, login failed","Keyエラー、ログイン失敗","로그인 실패입니다. 키가 잘못되었습니다"},
{"LOGIN_ERR_ENTER_QUEUE",1002,0,"登录失败,进入登录排队","登入失敗，進入登入佇列","Failed. Joining login queue","ログインに失敗しました。待機列に入ります","Failed. Joining login queue"},
{"LOGIN_ERR_QUEUE_FULL",1003,0,"登录失败,登录排队队列已满","登入失敗，登入佇列已滿","Failed. Login queue is full","ログインに失敗しました。待機列が上限に達しています","Failed. Login queue is full"},
{"SIT_ERR_SEATID",1050,nil,"座位id不合法","座位無效","Invalid seat","無効な席です","좌석 ID가 유효하지 않습니다"},
{"SIT_ERR_ALREADY_SITED",1051,nil,"已经在坐下","您已入座","You are already seated","すでに着席しています","이미 착석했습니다"},
{"SIT_ERR_SEAT_NOT_EMPTY",1052,nil,"座位已经有人","該座位已有玩家","Seat already taken","この席には他のプレイヤーがいます","좌석에 이미 사람이 있습니다"},
{"SIT_ERR_TABLE_FULL",1053,nil,"桌子已满","牌桌已滿","Table is full","テーブルが満席です","테이블이 가득찼습니다"},
{"STAND_ERROR",1100,nil,"站起错误","站起錯誤","Stand-up error","離席エラー","일어서기 오류입니다"},
{"NO_CHIPS_STAND",1101,nil,"筹码不足被强制站起","籌碼不足，已被強制站起","You have stood up due to insufficient chips","チップ不足のため、強制的に離席しました","칩이 부족해 강제로 일어섰습니다"},
{"NO_ACTION_STAND",1102,nil,"未操作自动站起","長時間未操作，已自動站起","You have stood up due to prolonged inactivity","長時間操作がなかったため、離席しました","조작하지 않아 자동으로 일어섰습니다"},
{"KICKED_STAND",1103,nil,"被踢站起","被移出牌桌，已被強制站起","You have stood up due to being removed from the table","テーブルから退出させられたため、強制的に離席しました","강제 퇴장당해 일어섰습니다"},
{"ALREADY_IN_ROOM",1150,nil,"已经在房间","已在房間內","Already in the room","すでにルーム内にいます","이미 방에 있습니다"},
{"ROOM_VERSION_TOO_HIGH",1151,nil,"房间版本高于客户端版本,需要升级客户端","房間版本高於客戶端版本，請更新客戶端","Room version is newer than your client. Please update your client","ルームのバージョンがクライアントより高いです。クライアントを更新してください","방 버전이 클라이언트 버전보다 높아 클라이언트 업그레이드가 필요합니다"},
{"ROOM_VERSION_TOO_LOW",1152,nil,"房间版本低于客户端版本,无法进入房间","房間版本過低，無法進入","Room version is too low, unable to enter","ルームのバージョンが低すぎるため、入室できません","방 버전이 클라이언트 버전보다 낮아 방에 입장할 수 없습니다"},
{"ROOM_HOTFIX",1153,nil,"房间热更中","房間維護中","Room under maintenance","ルームはメンテナンス中です","방 핫픽스 중입니다"},
{"ROOM_NOT_EXIST",1154,nil,"进入房间失败，房间不存在","房間不存在","Room does not exist","ルームが存在しません","입장할 수 없습니다. 방이 존재하지 않습니다."},
{"FRIEND_ROOM_FULL",1155,nil,"加入好友房失败，房间已满员","房間人數已滿","Room is full","ルームの人数が上限に達しています","친구방에 입장할 수 없습니다. 방이 만석입니다."},
{"FRIEND_ROOM_WILL_DISBAND",1156,nil,"加入好友房失败，房间即将解散","房間即將關閉","Room will close soon","ルームは間もなく閉鎖されます","친구방에 입장할 수 없습니다. 방이 곧 해산됩니다."},
{"ALLIN_ROOM_WILL_DISBAND",1157,nil,"加入ALLIN房间失败，房间即将解散","房間即將解散","Room will be disbanded soon","ルームは間もなく解散します","올인 포커 플레이 방에 입장할 수 없습니다. 방이 곧 해산됩니다."},
{"USER_LEVEL_NOT_MATCH_ROOM",1158,nil,"玩家等级与房间准入等级不匹配","等級未達房間准入等級","Your player level does not meet the entry requirements","プレイヤーレベルとルーム参加レベル条件が一致しません",nil},
{"REBY_ERR_CANNOT_REBY",1200,nil,"不能reby(还有筹码或没有座位)","無法重新買入（尚有籌碼或沒有座位）","Unable to rebuy (still have chips or no available seat)","rebuyできません（チップが残っている、または席がありません）","리바이할 수 없습니다 (칩이 남아있거나 자리가 없습니다)"},
{"REBY_ERR_STAND_SUCCESS",1201,nil,"不reby站起成功","已站起，無法重新買入","Already stood up, unable to rebuy","すでに離席したためrebuyできません","리바이하지 않고, 일어섰습니다."},
{"REBY_ERR_TOO_MUCH_CHIPS",1202,nil,"您当前带入筹码已达上限,无法进行补码","您當前帶入的籌碼已達上限，無法進行補碼","Max buy-in reached. Unable to add more chips","チップ所持上限数に達しているため、補充できません",nil},
{"ERR_BAG_FULL",1250,nil,"背包已满","背包已滿","Backpack is full","バッグがいっぱいです","가방이 가득 찼습니다"},
{"ERR_ITEM_CONFIG_NOT_FIND",1251,nil,"道具配置不存在","道具不存在","Item does not exist","アイテムが存在しません","아이템 설정이 존재하지 않습니다"},
{"ERR_ITEM_NOT_ENOUGHT",1252,nil,"道具数量不足","道具不足","Insufficient items","アイテムが足りません","아이템 수량이 부족합니다"},
{"ERR_ITEM_RECYCLE_FAIL",1253,nil,"道具回收失败","道具回收失敗","Failed to recycle items","アイテム回収に失敗しました","아이템 회수 실패입니다"},
{"ERR_ROLE_NAME_INVAILD",1254,nil,"牌手名称不合法","牌手名稱不合法","Invalid character name","キャラクター名が無効です","캐릭터 이름이 유효하지 않습니다"},
{"ERR_ROLE_NOT_OWNED",1255,nil,"未拥有牌手","未獲得該牌手","Character not obtained","このキャラクターを獲得していません","해당 캐릭터가 없습니다"},
{"ERR_SKIN_NOT_OWNED",1256,nil,"未拥有皮肤","未獲得該造型","Outfit not obtained","このスキンを獲得していません","해당 캐릭터 스킨이 없습니다"},
{"ERR_ROLE_GIFT_REACH_MAX_TIMES",1257,nil,"送礼次数达到上限","送禮次數已達上限","Gift limit reached","ギフト贈呈回数が上限に達しました","선물 횟수가 최대치에 도달했습니다"},
{"ERR_NOT_REACH_AWAKEN_LEVEL",1258,nil,"未达到誓约等级","未達到誓約等級","Not eligible to make a vow","誓約レベルに達していません","서약 레벨에 도달하지 않았습니다"},
{"ERR_ROLE_ALREADY_AWAKEN",1259,nil,"牌手已经誓约过","已誓約","Already made a vow","すでに誓約済みです","캐릭터가 이미 서약했습니다"},
{"ERR_LACK_AWAKEN_ITEM",1260,nil,"缺少誓约道具","缺少誓約道具","Insufficient Oath items","誓約アイテムが足りません","서약 아이템이 부족합니다"},
{"ERR_ROLE_REACH_MAX_LEVEL",1261,nil,"送礼失败，牌手已达到最高等级","牌手已滿級","Max level reached","キャラクターはすでに最大レベルです","선물할 수 없습니다. 캐릭터가 이미 최고 레벨에 도달했습니다."},
{"ERR_EMOJI_NOT_OWNED",1262,nil,"未拥有表情","未獲得該表情","Emote not obtained","このエモートを獲得していません","이모티콘이 없습니다"},
{"ERR_CHAT_NOT_OWNED",1263,nil,"未拥有快捷短语","未獲得該快捷短语","Quick Chat message not obtained","このクイックチャットを獲得していません","퀵 채팅이 없습니다"},
{"ERR_AVATAR_NOT_OWNED",1264,nil,"未拥有头像","未獲得該頭像","Avatar not obtained","このアバターを獲得していません","아바타가 없습니다"},
{"ERR_FRAME_NOT_OWNED",1265,nil,"未拥有头像框","未獲得該頭像框","Avatar Frame not obtained","このフレームを獲得していません","아바타 프레임이 없습니다"},
{"ERR_TITLE_NOT_OWNED",1266,nil,"未拥有称号","未獲得該稱號","Title not obtained","この称号を獲得していません","칭호가 없습니다"},
{"ERR_ROLE_ALREADY_FAVORITE",1267,nil,"牌手已被收藏","已收藏該牌手","Already added to Favorites","このキャラクターはすでに収集済みです","이미 즐겨찾기에 추가된 캐릭터입니다"},
{"ERR_FAVORITE_ROLE_LIMIT",1268,nil,"收藏牌手已达上限","收藏牌手欄位已滿","Favorites slots full","コレクションキャラクター枠が上限に達しました","즐겨찾기 캐릭터가 최대치에 도달했습니다"},
{"ERR_OUT_FITS_NOT_OWNED",1269,nil,"未拥有装饰物品","未獲得該裝飾品","Decoration not obtained","このデコレーションを獲得していません","장식 아이템이 없습니다"},
{"ERR_DECORATION_SCHEME_NOT_EXIST",1270,nil,"装饰方案不存在","裝飾方案不存在","Decor. Plan does not exist","デコプランが存在しません",nil},
{"ERR_DELETE_USING_DECORATION_SCHEME",1271,nil,"不能删除当前使用的方案","無法刪除目前正在使用的方案","This plan is currently in use and cannot be deleted","現在使用中のプランは削除できません",nil},
{"ERR_SNG_NOT_AVAILABLE",1350,nil,"SNG比赛未开放","SNG賽事尚未開放","SNG is not available yet","SNG試合は開放されていません",nil},
{"ERR_SNG_VERSION_NOT_MATCH",1351,nil,"SNG版本与玩家版本不匹配","SNG版本與當前版本不一致","Your SNG version does not match the current game version","SNGバージョンとクライアントバージョンが一致しません",nil},
{"ERR_SNG_SIGN_FAILED",1352,nil,"SNG报名失败","SNG報名失敗","SNG registration failed.","SNG登録に失敗しました。",nil}
}
    for _, v in pairs(bodys) do
        local m = {}
        for i, k in pairs(keys) do
            m[k] = v[i]
        end
        P[v[1]] = m
        PL[#PL+1] = m
    end
end
_initData()

tpl_RetCode = P
tpl_RetCode_list = PL
function tpl_RetCode_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P