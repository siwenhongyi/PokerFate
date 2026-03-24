-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','code','tip','zh','tw','en','jp','ko',}
    local bodys = {
{"HTTP_RET_OK",0,nil,nil,nil,nil,nil,nil},
{"HTTP_ERR",-1,nil,"系统默认错误(包含未知错误)","系統預設錯誤（包含未知錯誤）","System error (including unknown errors)","システムデフォルトエラー（未知のエラーを含む）","시스템 기본 오류입니다 (알 수 없는 오류 포함)"},
{"HTTP_AUTHENTICATION_FAILED",-2,nil,"login.authorization 验证失败","login.authorization 驗證失敗","login.authorization verification failed","login.authorization 認証失敗","login.authorization 인증 실패입니다"},
{"HTTP_INVALID_PARAM",-3,nil,"参数错误","參數錯誤","Invalid parameters","パラメータエラー","매개변수 오류입니다"},
{"HTTP_CONCURRENCY_LIMIT",-4,0,nil,nil,nil,nil,nil},
{"HTTP_SERVER_STOP",-50,nil,"服务器停服","伺服器維護中","Server under maintenance","サーバーメンテナンス","서버 점검 중입니다"},
{"HTTP_REGION_NOT_SUPPORTED",-51,nil,"地区未支持","目前地區不可用","Service not available in current region","現在の地域では利用できません","서비스 지역이 아닙니다"},
{"HTTP_IP_BLOCKED",-52,nil,"账号被封禁，有任何反馈建议可联系客服","帳號已被封禁，如有任何回饋或建議，請聯絡客服","Your account has been banned. Please contact Customer Support for assistance","アカウントが利用停止となっています。ご不明な点がございましたら、カスタマーサポートまでご連絡ください","계정이 차단되었습니다"},
{"HTTP_IMEI_BLOCKED",-53,nil,"设备号被封禁","裝置禁止存取","Device access denied","デバイスのアクセスが禁止されています","기기가 차단되었습니다"},
{"HTTP_ACCOUNT_BLOCKED",-54,nil,"账号被封禁","帳號已被封鎖","Account banned","アカウント停止中","계정이 차단되었습니다"},
{"HTTP_ACCOUNT_REGISTERED",-55,nil,"账号已经注册","帳號已存在","Account already exists","アカウントは既に存在します","이미 등록된 계정입니다"},
{"HTTP_ACCOUNT_NOT_FOUND",-56,nil,"账号不存在","帳號未註冊","Account not registered","アカウントが未登録です","존재하지 않은 계정입니다"},
{"HTTP_INVALID_EMAIL",-65,nil,"邮箱格式不对","信箱格式錯誤","Invalid email format","メール形式が正しくありません","이메일 형식이 틀렸습니다"},
{"HTTP_INVALID_EMAIL_PASSWORD",-66,nil,"密码不对","密碼錯誤","Incorrect password","パスワードが間違っています","비밀번호가 틀렸습니다"},
{"HTTP_INVALID_EMAIL_PASSWORD_FORMAT",-67,nil,[[密码格式不对。
6-12位数字、字母或符号。]],[[密碼格式錯誤。
6～12 位數字、英文字母或符號。]],[[Invalid password format.
6–12 characters (numbers, letters, and/or symbols).]],[[パスワード形式が正しくありません!
6〜12文字の英数字または記号.]],"비밀번호 형식이 틀렸습니다"},
{"HTTP_INVALID_EMAIL_CAPTCHA",-68,nil,"验证码不正确","驗證碼錯誤","Invalid verification code","確認コードが間違っています","인증코드가 올바르지 않습니다"},
{"HTTP_REGISTER_CAPTCHA_LIMIT",-69,nil,"验证码发送限制","驗證碼發送次數已達上限","Verification code sending limit reached","確認コード送信回数が上限に達しました","인증코드 발송이 제한되었습니다"},
{"HTTP_EMAIL_VERIFICATION_FAILED",-70,nil,"邮箱账号验证失败","信箱驗證失敗","Email verification failed","メール認証に失敗しました","이메일 계정 인증이 실패했습니다"},
{"HTTP_ACCOUNT_NO_EMAIL",-71,nil,"账号未绑定邮箱","未綁定信箱","Email not linked","メールが連携されていません","계정에 이메일이 연결되지 않았습니다"},
{"HTTP_EMAIL_HAS_ACCOUNT",-72,nil,"邮箱已绑定账号","信箱已被使用","Email already in use","メールアドレスはすでに使用されています","이미 계정이 연결된 이메일입니다"},
{"HTTP_CAPTCHA_TIMEOUT",-73,nil,"验证码超时","驗證碼已失效","Verification code expired","確認コードの有効期限が切れています","인증코드 시간이 초과되었습니다"},
{"HTTP_REGISTER_LIMIT",-74,nil,"登录排队中 无法注册","登入失敗，伺服器繁忙，請稍後再試","Login failed. The server is busy. Please try again later","サーバーが混雑しているため、ログインに失敗しました。後ほどお試しください",[[注册失败，服务器繁忙，请稍后再试",]]},
{"HTTP_STOVE_HAS_ACCOUNT",-75,nil,"Stvoe账号已被使用","Stvoe帳號已被使用","Stvoe account already in use","Stvoeアカウントはすでに使用されています","Stvoe账号已被使用"},
{"HTTP_ACCOUNT_DELETED",-76,nil,"账号不存在","帳號未註冊","Account not registered","アカウントが未登録です","존재하지 않은 계정입니다"},
{"HTTP_IMEI_LOGIN_NUM_LIMIT",-77,nil,"进入游戏失败，本设备登录账号个数已超上限。","登入失敗，此裝置已達可登入帳號上限","Failed. This device has reached the max number of accounts","本端末でログイン可能なアカウント数の上限に達しています","imei当天登录设备数量超过限制"},
{"HTTP_STEAM_OFFLINE_ERR",-78,nil,"Steam登录已过期，请重新登录后重试","Steam登入已過期，請重新登入後重試","Your Steam session has expired. Please log in again","Steamのセッションが切れました。再ログインしてください","steam处于离线状态"},
{"HTTP_STEAM_IP_LIMIT_ERR",-79,nil,"服务器繁忙，请稍后再试","伺服器繁忙，請稍後再試","The server is busy. Please try again later","サーバーが混雑しています。しばらくしてから再度お試しください","steam请求限制ip中"},
{"HTTP_STEAM_LOGIN_TIME_OUT_ERR",-80,nil,"Steam登录已过期，请重新登录后重试","Steam登入已過期，請重新登入後重試","Your Steam session has expired. Please log in again","Steamのセッションが切れました。再ログインしてください","steam处于离线状态"},
{"HTTP_STEAM_CREATE_ORDER_TIME_OUT_ERR",-81,nil,"服务器繁忙，请稍后再试","伺服器繁忙，請稍後再試","The server is busy. Please try again later","サーバーが混雑しています。しばらくしてから再度お試しください","steam请求限制ip中"},
{"HTTP_STEAM_FINISH_ORDER_TIME_OUT_ERR",-82,nil,"订单处理中，请稍候…","訂單處理中，請稍候…","Processing order. Please wait...","注文を処理しています。しばらくお待ちください","steam完成订单请求超时"},
{"HTTP_COLL_CARD_LIMIT",-150,nil,"收藏达上限","收藏已達上限","Hand Replay limit reached","コレクション数が上限に達しました","수집 한도에 도달했습니다"},
{"HTTP_COLL_CARD_DETAIL_ERR",-151,nil,"牌局正在结算，请稍等...","牌局正在結算，請稍候...","The game is being settled, please wait...","試合を決着させようとしています。お待ちください...","牌局正在结算，请稍等..."},
{"HTTP_NICKNAME_INVALID_LENGTH",-200,nil,"昵称长度不符合","暱稱長度不符合要求","Nickname length requirement not met","ニックネームの長さが要件を満たしていません","닉네임 길이가 올바르지 않습니다"},
{"HTTP_NICKNAME_NOT_ALL_NUMERIC",-201,nil,"昵称不可为纯数字","暱稱不可為純數字","Nickname cannot contain only numbers","数字のみのニックネームは使用できません","닉네임은 숫자만으로 설정할 수 없습니다"},
{"HTTP_NICKNAME_CANNOT_BE_EMAIL",-202,nil,"昵称不可为邮箱格式","暱稱不可為信箱格式","Nickname cannot be in email format","メールアドレスをニックネームにすることはできません","닉네임은 이메일 형식일 수 없습니다"},
{"HTTP_NICKNAME_ALREADY_EXISTS",-203,nil,"昵称已被占用","暱稱已被使用","Nickname already taken","このニックネームはすでに使用されています","이미 사용 중인 닉네임입니다"},
{"HTTP_NICKNAME_INVALID_CHARACTERS",-204,nil,"昵称包含敏感词","暱稱含違規內容","Nickname contains inappropriate content","ニックネームに不適切な内容が含まれています","닉네임에 금칙어가 포함되어 있습니다"},
{"HTTP_NICKNAME_INSUFFICIENT_ITEM",-205,nil,"昵称修改道具不足","改名道具不足","Insufficient rename items","名前変更用アイテムが足りません","닉네임 변경 아이템이 부족합니다"},
{"HTTP_NICKNAME_UNCHANGED",-206,nil,"昵称无修改","暱稱未作修改","No changes made to nickname","ニックネームは変更されていません","닉네임 변경사항이 없습니다"},
{"HTTP_DECLARATION_INVALID_LENGTH",-207,nil,"个人宣言长度不符合","個人狀態長度不符合要求","Bio length requirement not met","ステータスの長さが要件を満たしていません","개인 상태메시지 길이가 올바르지 않습니다"},
{"HTTP_DECLARATION_INVALID_CHARACTERS",-208,nil,"个人宣言包含非法字符","個人狀態包含非法字元","Bio contains illegal characters","ステータスに使用できない文字が含まれています","개인 상태메시지에 유효하지 않은 문자가 포함되었습니다"},
{"HTTP_ROLE_NICKNAME_INVALID_LENGTH",-209,nil,"牌手昵称长度不符合","牌手暱稱長度不符合要求","Character nickname length requirement not met","キャラクターニックネームの長さが要件を満たしていません","캐릭터 닉네임 길이가 올바르지 않습니다"},
{"HTTP_ROLE_NICKNAME_INVALID_CHARACTERS",-210,nil,"牌手昵称包含非法字符","牌手暱稱包含非法字元","Character nickname contains illegal characters","キャラクターニックネームに使用できない文字が含まれています","캐릭터 닉네임에 허용되지 않는 문자가 포함되어 있습니다"},
{"HTTP_DRAW_WEIGHTS_LACK",-300,nil,"全类别权重数组为空","All weight arrays are empty","All weight arrays are empty","All weight arrays are empty","전체 카테고리 가중치 배열이 비어있습니다"},
{"HTTP_DRAW_CHARACTER_WEIGHTS_LACK",-301,nil,"牌手类别权重数组为空","Character weight array is empty","Character weight array is empty","Character weight array is empty","캐릭터 카테고리 가중치 배열이 비어있습니다"},
{"HTTP_DRAW_UP_CHARACTER_WEIGHTS_LACK",-302,nil,"up牌手类别权重数组为空","UP character weight array is empty","UP character weight array is empty","UP character weight array is empty","up 캐릭터 카테고리 가중치 배열이 비어있습니다"},
{"HTTP_DRAW_OTHER_WEIGHTS_LACK",-303,nil,"非牌手类别权重数组为空","Non-character weight array is empty","Non-character weight array is empty","Non-character weight array is empty","비캐릭터 카테고리 가중치 배열이 비어있습니다"},
{"HTTP_DRAW_WEIGHTS_RAND_LACK",-304,nil,"全类别权重数组随机失败","Failed to randomize all weight arrays","Failed to randomize all weight arrays","Failed to randomize all weight arrays","전체 카테고리 가중치 배열이 랜덤으로 실패했습니다"},
{"HTTP_DRAW_SERVER_LIMIT",-305,nil,"服务器繁忙","伺服器繁忙","Server busy","サーバーが混雑しています","서버가 혼잡합니다"},
{"HTTP_FRIENDS_LIMIT",-350,nil,"对方好友数量达上限","對方好友數量已達上限","The other player's friend list is full","相手のフレンド数が上限に達しています","상대방의 친구 수가 최대치에 도달했습니다"},
{"HTTP_FRIENDS_MARk_ERR",-351,nil,"备注失败","備註失敗","Failed to add remark","備考を設定できません","메모 실패입니다"},
{"HTTP_FRIENDS_DEL_ERR",-352,nil,"删除失败","刪除好友失敗","Failed to remove friend","フレンド削除に失敗しました","삭제 실패입니다"},
{"HTTP_FRIENDS_UNBLOCKED_DEL_ERR",-353,nil,"移除拉黑互删失败","解除黑名單並刪除好友失敗","Failed to remove from blacklist and delete friend","ブラックリスト解除およびフレンド削除に失敗しました","차단 해제 및 상호 삭제 실패입니다"},
{"HTTP_FRIENDS_UNBLOCKED_ERR",-354,nil,"移除拉黑失败","移除黑名單失敗","Failed to remove from blacklist","ブラックリスト解除に失敗しました","차단 해제 실패입니다"},
{"HTTP_FRIENDS_BLOCKED_ERR",-355,nil,"拉黑失败","加入黑名單失敗","Failed to add to blacklist","ブラックリスト追加できませんでした","차단 실패입니다"},
{"HTTP_FRIENDS_SELF_LIMIT",-356,nil,"好友数量达上限","好友數量已達上限","Friend list is full","フレンド数が上限に達しています","친구 수가 최대치에 도달했습니다"},
{"HTTP_FRIENDS_BLOCKED_LIMIT",-357,nil,"黑名单数量已达上限！","你的黑名单數已達上限！","Blacklist is full!","ブラックリスト数が上限に達しました","친구 목록이 가득찼습니다!"},
{"HTTP_SHOP_CONFIG_NOT_EXIST",-400,nil,"商品配置无效","商品不存在","Item does not exist","商品が存在しません","상품 설정이 유효하지 않습니다"},
{"HTTP_SHOP_RECHARGE_FAILED",-401,nil,"购买失败","購買失敗","Purchase failed","購入できませんでした","구매 실패입니다"},
{"HTTP_SHOP_REPEAT_REFUND",-402,nil,"限购商品重复购买，自动退款","重複購買的商品已退款","Duplicate purchase refunded","重複購入した商品は返金されました","한정 상품 중복 구매로 자동 환불됩니다"},
{"HTTP_SHOP_PURCHASE_LIMIT",-403,nil,"商品已售罄！","商品已售罄！","Already sold out!","商品は完売しました","商品已售罄！"},
{"HTTP_SHOP_COST_NOT_ENOUGH",-404,nil,"购买消耗的道具不足","購買所需消耗的道具不足","Insufficient items to purchase","購入に必要な消費アイテムが足りません","구매에 필요한 아이템이 부족합니다"},
{"HTTP_SHOP_REWARD_CLAIMED",-405,nil,"奖励在限制时间内已领取","獎勵已領取","Reward already claimed","報酬はすでに受け取り済みです","제한 시간 내에 이미 보상을 받았습니다"},
{"HTTP_SHOP_UNAVAILABLE",-406,nil,"商品已下架！","商品已下架！","Currently unavailable!","商品は販売停止しました","商品已下架！"},
{"HTTP_MAIL_PACK_FULL_ERR",-500,nil,"背包已满","背包已滿","Backpack is full","バッグがいっぱいです","가방이 가득찼습니다"},
{"HTTP_SEVEN_SIGN_MISS_FULL_ERR",-550,nil,"补签次数已满","補簽次數已用盡","No remaining make-up attempts","補填回数を使い果たしました","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_MONTHLY_REWARD_ERR",-551,nil,"月卡签到奖励配置错误","月卡簽到獎勵不存在","Shark Pass check-in reward does not exist","月間パスログイン報酬が存在しません","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_UPDATE_REWARD_ERR",-552,nil,"月卡签到奖励更新失败错误","月卡簽到獎勵更新失敗","Failed to update Shark Pass check-in rewards","月間パスログイン報酬を更新できませんででした","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_CONF_ERR",-553,nil,"签到配置错误","簽到設定異常","Check-in configuration error","ログイン設定エラー","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_CONF_REWARD_ERR",-554,nil,"签到奖励配置错误","簽到獎勵不存在","Check-in reward does not exist","ログイン報酬が存在しません","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_TOTAL_REWARD_ERR",-555,nil,"签到累计奖励配置错误","簽到累計獎勵不存在","Cumulative check-in reward does not exist","累計ログイン報酬が存在しません","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_CREATE_ERR",-556,nil,"签到记录新增失败错误","簽到記錄更新失敗","Failed to update check-in record","ログイン記録を更新できませんでした","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_EXIST_ERR",-557,nil,"已存在签到错误","簽到錯誤","Check-in error","ログインエラー","보충 출석 횟수가 가득찼습니다"},
{"HTTP_SEVEN_SIGN_EXPIRED_ERR",-558,nil,"月卡已过期","月卡已過期","Shark Pass has expired","月間パスは期限切れです","Shark Pass has expired"},
{"HTTP_NEWBIE_NICKNAME_ERR",-600,nil,"暂无可用昵称，请自行输入。","暫無可用暱稱，請自行輸入。","No nickname available. Please enter one.","使用できるニックネームが見つからないため、ご自身で入力してください","사용 가능한 닉네임이 없습니다. 직접 입력해 주세요."},
{"HTTP_VIP_REWARD_CLAIMED",-650,nil,"VIP奖励已领取","VIP獎勵已領取","VIP Reward already claimed","VIP報酬は受け取り済みです","VIP Reward already claimed"},
{"REDEMPTION_CODE_EX_ERR",-700,0,"礼品码有误，请再次确认","禮品碼錯誤，請再次確認","Invalid code. Please check and try again","ギフトコードが正しくありません。コードを確かめ、もう一度お試しください。","Invalid code, please check again"},
{"REDEMPTION_CODE_EXPIRED_ERR",-701,0,"礼品码已过期","禮品碼已過期","Gift code has expired","ギフトコードは期限切れです","Gift code has expired"},
{"REDEMPTION_CODE_NOT_FOUND_ERR",-702,0,"礼品码有误，请再次确认","禮品碼錯誤，請再次確認","Invalid code. Please check and try again","ギフトコードが正しくありません。コードを確かめ、もう一度お試しください。","Invalid code, please check again"},
{"REDEMPTION_CODE_USED_ERR",-703,0,"礼品码已兑换","禮品碼已兌換","Gift code has been redeemed","ギフトコードはすでに使用済みです","Gift code has been redeemed"},
{"REDEMPTION_CODE_LIMIT_ERR",-704,0,"兑换次数已达上限","禮品碼兌換次數已達上限","Gift code redemption limit reached","ギフトコードの引き換え回数が上限に達しました","Gift code redemption limit reached"},
{"REDEMPTION_CODE_CON_ERR",-705,0,"抱歉，您不符合领取条件！","抱歉，您不符合領取條件！","Not eligible to redeem this gift.","利用条件を満たしていません。","Not eligible to redeem this gift."},
{"HTTP_ASSOC_USER_CHNL_ERR",-750,nil,"渠道错误 不是符合条件的渠道","渠道錯誤 不是符合條件的渠道","Channel error: Not an eligible channel","チャネルエラー 適格なチャネルではありません","渠道错误 不是符合条件的渠道"},
{"HTTP_ASSOC_USER_ALREADY_BIND",-751,nil,"账号已绑定过关联账号","賬號已綁定過關聯賬號","Account has already bound a linked account","アカウントは既に関連アカウントをバインド済みです","账号已绑定过关联账号"},
{"HTTP_ASSOC_USER_ERR_NUM_LIMIT",-752,nil,"错误次数超过限制","錯誤次數超過限制","Number of errors exceeds limit","エラー回数が制限を超えました","错误次数超过限制"},
{"HTTP_ASSOC_USER_HAS_EMAIL",-753,nil,"账号绑定了邮箱 无法关联其他账号","賬號綁定了郵箱 無法關聯其他賬號","Account is bound to email; cannot link other accounts","アカウントはメールにバインドされているため、他のアカウントを関連付けできません","账号绑定了邮箱 无法关联其他账号"},
{"HTTP_ASSOC_USER_NOT_STOVE",-754,nil,"账号不是stove类型 无法关联其他账号","賬號不是stove類型 無法關聯其他賬號","Account is not a Stove type; cannot link other accounts","アカウントはStoveタイプではないため、他のアカウントを関連付けできません","账号不是stove类型 无法关联其他账号"},
{"HTTP_ASSOC_USER_NOT_EMAIL",-755,nil,"账号不是邮箱类型 无法生成关联密码","賬號不是郵箱類型 無法生成關聯密碼","Account is not an email type; cannot generate link password","アカウントはメールタイプではないため、関連パスワードを生成できません","账号不是邮箱类型 无法生成关联密码"},
{"HTTP_ASSOC_USER_NOT_EXIST",-756,nil,"关联的账号不存在","關聯的賬號不存在","Linked account does not exist","関連するアカウントが存在しません","关联的账号不存在"},
{"HTTP_ASSOC_USER_PWD_ERR",-757,nil,"关联的账号密码错误","關聯的賬號密碼錯誤","Linked account password is incorrect","関連するアカウントのパスワードが間違っています","关联的账号密码错误"},
{"HTTP_ASSOC_USER_PWD_INVALID",-758,nil,"设置关联密码格式错误","設置關聯密碼格式錯誤","Link password format error","関連パスワードのフォーマットエラー","设置关联密码格式错误"},
{"HTTP_ASSOC_USER_FAIL",-759,nil,"关联失败","關聯失敗","Link failed","関連付けに失敗しました","关联失败"},
{"HTTP_INSUFFICIENT_ITEM",-800,nil,"开启红包道具不足","开启红包道具不足","开启红包道具不足","开启红包道具不足","开启红包道具不足"}
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

tpl_HttpCode = P
tpl_HttpCode_list = PL
function tpl_HttpCode_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

