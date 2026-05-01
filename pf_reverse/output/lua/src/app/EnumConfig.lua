-- 枚举定义

-- 道具大分类
GPropType = {
    Consume = 1,    -- 消耗类
    Display = 2,   -- 装饰类
}

-- 道具小分类
GPropKind = {
    Gold = 101, -- 金币
    TicketDraw = 102,   -- 抽奖券
    TicketDress = 103,   -- 服饰券
    TicketRole = 104,   -- 角色兑换券
    PieceDress = 105,   -- 分解后的道具碎片
    Gift = 106,         -- 礼物
    PieceAwaken = 107,   -- 装饰碎片，觉配材料
    PieceRole = 108,   -- 角色碎片，觉配材料
    ChangeName = 109,   -- 改名卡
    Cumulative = 110,   -- 累计数量值
    Show = 111,         -- 展示类道具
    ExpCard = 112,      -- 经验卡
    TournamentTicket = 113,    -- 赛事门票

    Avatar = 201,       -- 头像
    FrameAvatar = 202,  -- 头像框
    FrameName = 203,    -- 名字框
    Title = 204,        -- 称号
    CardBack = 205,     -- 牌背
    Table = 206,        -- 牌桌
    MusicLobby = 207,   -- 音乐 大厅
    MusicTable = 208,   -- 音乐 对战
    LobbyScene = 209,   -- 大厅背景
    AllInEff = 210,     -- all in特效
    NameplateEff = 211, -- 铭牌特效
    CardFace = 212,     -- 牌面

    Box = 301,          -- 普通礼包
    RandomBox = 302,    -- 随机礼包
    OptionalBox = 303,  -- 自选礼包
}

-- 道具ID
GPropId = {
    None = 0,               -- 无
    Gold = 10100001,        -- 金币
    TicketDraw = 10200001,  -- 轮盘彩晶
    TicketDress = 10300001, -- 服饰黑卡
    TicketHotSpring = 10410001,   -- 温泉季 角色兑换券
    FirePower = 11000010,   -- 火力值
    ChampionPoints = 11000011, -- 冠军积分道具
    Exp = 11000020,         -- 经验
    ExpSNG = 11000021,         -- 经验 SNG
    Bond = 11000030,        -- 好感度
    BondSNG = 11000031,        -- 好感度 SNG
    ActivePoint = 11000040, -- 日常活跃点
    WeeklyPoint = 11000041, -- 周常活跃点
    ChallengePoint = 11000042,  -- 挑战活跃点
    GiftFragment = 10500001,    -- 礼物碎片

    DrawCoin = 10200001,    -- 轮盘彩晶
    DrawTicket = 10200002,  -- 结缘芯片

    ChangeName = 10900001,   -- 改名卡
    ExchangeCoin = 10400001,    -- 兑换券

    Retroactive = 11100001,     -- 补签权益
    ExclusiveTask = 11100002,   -- 专属任务
    MonthlyCard = 11100003,     -- 月卡
    SNGChip = 11100004,         -- SNG筹码
    ReSign = 10900002,          -- 改签名

    FestivalRedPacket = 10420001, --春节红包

    RoleGiftBox = 30300001,      -- 自选彩色礼包

    CharacterEmojiId = 11100101,  -- 角色通用表情道具
    CharacterVoiceId2 = 11100201,  -- 角色通用语音道具 2
    CharacterVoiceId3 = 11100202,   -- 角色通用语音道具 3
    CharacterVoiceId4 = 11100203,   -- 角色通用语音道具 4 
    CharacterVoiceId5 = 11100204,   -- 角色通用语音道具 5
    CharacterVoiceId6 = 11100205,   -- 角色通用语音道具 6

    CharacterFileId1 = 11100301,   -- 角色专属档案道具 1
    CharacterFileId2 = 11100302,   -- 角色专属档案道具 2
    CharacterFileId3 = 11100303,   -- 角色专属档案道具 3
    CharacterFileId4 = 11100304,   -- 角色专属档案道具 4
    CharacterFileId5 = 11100305,   -- 角色专属档案道具 5
}

GPropQuality = {
    COLOR_0 = 0, -- 灰，无品质区分道具使用
    COLOR_1 = 1, -- 绿
    COLOR_2 = 2, -- 蓝
    COLOR_3 = 3, -- 紫
    COLOR_4 = 4, -- 橙
    COLOR_5 = 5, -- 彩
}

-- 商城配置奖励大类
GMajorType = {
    PROP = 1,       -- 道具
    ROLE = 2,       -- 角色
    ROLE_SKIN = 3,  -- 角色皮肤
}

------------------ 游戏定义 start ------------------
-- 房间模式类型 room_mode
GAME_ROOM_MODE = {
    LOBBY = 1,		-- 大厅
    PRIVATE = 2,    -- 私人
    SIDE_GAME = 3, -- side game
}

-- 房间游戏玩法 room_type
GAME_ROOM_TYPE = {
    NULL = 0,
    HOLDEM = 1,		-- poker
    OMAHA = 2,
    SLOTS = 3,
    ALLIN = 4,
}

-- 玩法类型 idx + RoomSubType*100 + RoomType*10000+room_mode*10000000
-- room_mode + RoomType + SubType + idx
GAME_GAME_TYPE = {
    TOURNAMENT = 1,     -- 比赛，用于 ui 判断

    LOBBY_HOLDEM_GAME   = 10010101, -- 大厅常规德州玩法
    LOBBY_HOLDEM_ALLIN = 10040101,  -- 大厅常规 all in or fold
    JACKPOT_HOLDEM_GAME = 10010202, -- 大厅jackpot德州玩法
    FRIEND_HOLDEM_GAME = 20010103, -- 好友房德州玩法
    SNG_HOLDEM_GAME     = 10050301,
    MTT_HOLDEM_GAME     = 10070401,
    ALLINFOLD_HOLDEM_GAME = 10010206, -- all in fold

    LOBBY_OMAHA_GAME    = 10020101, -- 大厅常规奥马哈玩法
    SNG_OMAHA_GAME      = 10060301,
    MTT_OMAHA_GAME      = 10070401,

    TRAINING_HOLDEM_GAME    = 40010101, -- 训练房德州德州玩法
    TRAINING_OMAHA_GAME     = 40020101, -- 训练房奥马哈玩法
    SNG_TRAIN_GAME      = 40050301, -- sng 训练场

    LOBBY_SLOTS_GAME        = 10030101, -- 大厅slots
    SIDE_GAME_COLOR_GAME    = 30030101, -- color game
    SIDE_GAME_SLOTS_GAME    = 30030102, -- side game slots
    SIDE_GAME_PINBALL_GAME = 30080101,  -- 弹球

    LOBBY_BLACKJACK_GAME    = 10040101, -- 大厅blackjack
    SIDE_GAME_BLACKJACK_GAME = 30040102,-- side game blackjack
}

-- 玩法子类型
GAME_SUB_TYPE = {
    RGL = 1, -- 常规玩法
    JPOT = 2, -- jackpot
    SNG = 3,
    NORMAL_MTT = 4, -- 普通MTT
    INSTANT_MTT = 5, -- 人满即开MTT
}

-- 大厅类型
LOBBY_ROOM_TYPE = { -- 普通、防作弊
    NORMAL = 0,
    ANTI_CHEATING = 1,
}

-- mtt 比赛类型
MTT_SUB_TYPE = {
    NORMAL = 0,	-- 普通
    GO = 1,		-- 人满即开
}

-- 座位状态
SEAT_ST = {
    HAS_PLAYER = 1,
    EMPTY_SIT = 2,
    EMPTY_INVITE = 3,
}

-- 牌桌动特效
ACTION_TYPE = {
    AllInEff = 1,
    NameplateEff = 2,
    CardFace = 3,
}

------------------ nlh start ------------------
POKER_ACTION = {
    NONE = 0,   -- 无人
	FOLD = 1,
	CHECK = 2,
	CALL = 3,
	RAISE = 4,
	WAIT = 5,  --等待bet
	SITED = 6, --坐下,未入局状态
	BET = 7,   --第一个加注
	SB = 8,    --下小盲
	BB = 9,    --下大盲
    ANTE = 10, -- 前注
    FORCE_BB = 11,  -- 强制 bb
    SYS_FOLD = 12, -- 系统自动弃牌
    SYS_CHECK = 13,    -- 系统自动过牌
    STRADDLE = 14,
    -- POT = 15,       -- 满 pot
    LEAVE_FOLD = 16,    -- 离开弃牌

    ALLIN = 17, -- 全下
}

POKER_ACTION_TAGS = {
    [POKER_ACTION.FOLD] = {name = "LAB_FOLD", bg = "InGame[ingame_action_05]", replayBg = "InGame[ingame_replay_action_05]"},
    [POKER_ACTION.CHECK] = {name = "LAB_CHECK", bg = "InGame[ingame_action_02]", replayBg = "InGame[ingame_replay_action_02]"},
    [POKER_ACTION.CALL] = {name = "LAB_CALL", bg = "InGame[ingame_action_04]", replayBg = "InGame[ingame_replay_action_04]", nameImg = "ingame_action_call_tw"},
    [POKER_ACTION.RAISE] = {name = "LAB_RAISE", bg = "InGame[ingame_action_04]", replayBg = "InGame[ingame_replay_action_04]", nameImg = "ingame_action_raise_tw"},
    [POKER_ACTION.BET] = {name = "LAB_BET", bg = "InGame[ingame_action_04]", replayBg = "InGame[ingame_replay_action_04]", nameImg = "ingame_action_bet_tw"},
    [POKER_ACTION.SB] = {name = "LAB_SMALL_BLIND", bg = "InGame[ingame_action_01]", replayBg = "InGame[ingame_replay_action_01]", nameImg = "ingame_action_sb_tw"},
    [POKER_ACTION.BB] = {name = "LAB_BIG_BLIND", bg = "InGame[ingame_action_01]", replayBg = "InGame[ingame_replay_action_01]", nameImg = "ingame_action_bb_tw"},
    [POKER_ACTION.ANTE] = {name = "LAB_ANTE", bg = "InGame[ingame_action_01]", replayBg = "InGame[ingame_replay_action_01]"},
    [POKER_ACTION.FORCE_BB] = {name = "LAB_BIG_BLIND", bg = "InGame[ingame_action_01]", replayBg = "InGame[ingame_replay_action_01]", nameImg = "ingame_action_bb_tw"},
    [POKER_ACTION.SYS_FOLD] = {name = "LAB_FOLD", bg = "InGame[ingame_action_05]", replayBg = "InGame[ingame_replay_action_05]"},
    [POKER_ACTION.SYS_CHECK] = {name = "LAB_CHECK", bg = "InGame[ingame_action_02]", replayBg = "InGame[ingame_replay_action_02]"},
    [POKER_ACTION.STRADDLE] = {name = "LAB_STRADDLE", bg = "InGame[ingame_action_01]", replayBg = "InGame[ingame_replay_action_01]"},
    -- [POKER_ACTION.POT] = {name = "LAB_POT", bg = "InGame[ingame_action_04]", replayBg = "InGame[ingame_replay_action_04]"},
    [POKER_ACTION.LEAVE_FOLD] = {name = "LAB_FOLD", bg = "InGame[ingame_action_05]", replayBg = "InGame[ingame_replay_action_05]"},
    [POKER_ACTION.ALLIN] = {name = "LAB_ALL_IN_LOWER", bg = "InGame[ingame_action_03]", replayBg = "InGame[ingame_replay_action_03]", nameImg = "ingame_action_allin_tw"},
}

POKER_ROUND = {
	PRE_FLOP = 1,
	FLOP = 2,
	TURN = 3,
	RIVER = 4,
	OVER = 5,
	FINISH = 6,  --结算阶段
}

POKER_TYPE = {
    NONE = 0, --小于5张牌，未成牌
    FOLD = -1, --弃牌
    HIGH_CARD = 1, --高牌
    ONE_PAIR = 2, --一对
    TWO_PAIR = 3, --两对
    THREE = 4, --三条
    STRAIGHT = 5, --顺子
    FLUSH = 6, --同花
    FULL_HOUSE = 7, --葫芦
    QUADS = 8, --四条
    STRAIGHT_FLUSH = 9, --同花顺
    ROYAL_FLUSH = 10, --皇家同花顺
}
POKER_TYPE_NAME = {
    [-1] = "LAB_FOLD",
    [0] = "",
	[1] = "LAB_HIGH_CARD",
	[2] = "LAB_ONE_PAIR",
	[3] = "LAB_TWO_PAIRS",
	[4] = "LAB_THREE_KIND",
	[5] = "LAB_STRAIGHT",
	[6] = "LAB_FLUSH",
	[7] = "LAB_FULL_HOUSE",
	[8] = "LAB_QUADS",
	[9] = "LAB_STRAIGHT_FLUSH",
	[10] = "LAB_ROYAL_FLUSH",
}

-- bet 刻度列表
POKER_BET_STEP = {
    {1,5},{1,4},{1,3},{2,5},{1,2},{3,5},{2,3},{3,4},{4,5},{1},{1.5},{2}
}
OMAHA_BET_STEP = {
    {1,5},{1,4},{1,3},{2,5},{1,2},{3,5},{2,3},{3,4},{4,5},{1}
}
POKER_BET_DEFAULT_VALUES = {3, 5, 7, 10}

-- raise 刻度
POKER_RAISE_STEP = {
    2,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3,3.5,4,4.5,5,5.5,6
}
OMAHA_RAISE_STEP = {
    2,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3,3.1,3.2,3.3,3.4,3.5,3.6,3.7,3.8,3.9,4
}
POKER_RAISE_DEFAULT_VALUES = {1, 6, 11, 13}
OMAHA_RAISE_DEFAULT_VALUES = {1, 6, 11, 21}

-- 底池加注刻度
POKER_RAISE_POT_STEP = {
    {1,5},{1,4},{1,3},{2,5},{1,2},{3,5},{2,3},{3,4},{4,5},{1},{1.5},{2}
}
OMAHA_RAISE_POT_STEP = {
    {1,5},{1,4},{1,3},{2,5},{1,2},{3,5},{2,3},{3,4},{4,5},{1}
}
POKER_RAISE_POT_DEFAULT_VALUES = {3, 5, 7, 10}

------------------ 聊天 start ------------------
CHAT_TYPE = {
	TEXT = 1,
	VOICE = 2,
}

-- 聊天语音类型
CHAT_VOICE_TYPE = {
    Card = 1,  -- 牌局语音
    Action = 2,  -- 牌局操作
    Game = 3,  -- 牌局触发语音
    Chat = 4,  -- 聊天快捷语
    Task = 5,  -- 任务面板语音
    Gain = 6,  -- 获得人物语音
    Login = 7,  -- 登录语音
    Lobby = 8,  -- 大厅交互语音
    Love1 = 9,  -- 赠送普通礼物语音
    Love2 = 10, -- 赠送喜欢礼物语音
    Bond = 11, -- 好感度升级
    Awaken = 12, -- 觉醒语音
}

-- 聊天语音 ui 分类
CHAT_VOICE_TAG = {
    Login = 1,  -- 登录 大厅
    Bond = 2,   -- 养成
    Game = 3,   -- 对局
    Card = 4,   -- 牌型
    Task = 5,   -- 任务
}

------------------ 颜色定义 ------------------
COLOR = {
    main_white = CU.Color(1,1,1),
    main_grey = CU.Color(0.4,0.4,0.4),
    main_red = CU.Color(1,0.3,0.3),
    main_green = CU.Color(0,0.8,0.53),
    main_orange = CU.Color(0.9,0.58,0.27),
}

------------------ 注册登录 ------------------
LOGIN_TYPE = {
    GUEST = 1,      -- 游客登录
    EMAIL = 2,      -- 邮箱登录
    FACEBOOK = 3,
    TWITTER = 4,    -- X（推特）登录
    iOS = 5,        -- 苹果登录
    STOVE = 6,      -- stove
    STOVE_PC = 7,    -- stove PC
    STEAM = 8,     -- steam
}

TOKEN_TYPE = {
    IMEI = 1,       -- 设备标识
    EMAIL = 2,      -- 邮箱
}

EMAIL_REGISTER_STEP = {
    CAPTCHA = 1,    -- 验证码确认
    PASSWORD = 2,   -- 密码确认
}

-- 找回步骤
RETRIEVE_STEP = {
    NAME = 1,       -- 昵称/UID/邮箱
    CAPTCHA = 2,    -- 验证码/邮箱
    MODIFY = 3,     -- 修改密码
}

-- 确认账号类型（找回密码）
RETRIEVE_TYPE = {
    UID = 1,
    EMAIL = 2,
    NICKNAME = 3,   -- 昵称
}

-- 注册登录类型
REGISTER_LOGIN__TYPE = {
    REGISTER = "register",
    LOGIN = "log",
}

------------------ 抽卡 ------------------
CARD_POOL_TYPE = {
    RESIDENT = 1,   -- 常驻
}

CARD_CONTENT_TYPE = {
    CHARACTER = 1,      -- 角色
    DECORATION = 2,     -- 装饰
    GIFT = 3,           -- 礼物
}

------------------ 大厅自动弹窗优先级 ------------------
LOBBY_POP_PRIORITY = {
    LevelUpgrade = 2000,  -- 升级
    SysOpen = 1900,  -- 功能解锁
    VipUp = 990,    -- vip 等级提升
    Bankrupt = 980, -- 破产保护
    BondUp = 970,   -- 好感度提升
    FestivalGift = 968, --活动礼包
    ActivityGift = 967,     -- 主题活动礼包
    ShopPush = 965,     -- 商店-新人优惠

    MonthlyCardEffect = 962,    -- 月卡获得特效
    RewardNew = 961,        -- 获得新道具
    Reward = 960,           -- 恭喜获得
    BackpackGift = 950,     -- 礼物礼包选择

    ActivityNewmanCheckin = 959, -- 新人签到活动
    RewardMonthlyCard = 958,    -- 月卡签到奖励
    SignIn = 950,   -- 每日签到
    Notice = 900,   -- 公告

    RoleLoginVoice = 500,   -- 角色登场语音

    ReviewScore = 0,    -- 系统评分
}

POP_TAG = {
    Reward = "Reward",  -- 奖励弹窗
}

------------------ 商店配置类型 ------------------
SHOP_TYPE = {
    first_recharge = 1,
    monthly_card = 2,
    shop_role_skin = 3,
    shop_gifts = 4,
    shop_gifts2 = 5,
    [5] = tpl_shop_gifts,
    shop_exchange = 6,
    shop_recharge = 7,
    shop_recharge2 = 8,
    [8] = tpl_shop_recharge,
    shop_recharge3 = 9,
    [9] = tpl_shop_recharge,
    quick_purchase = 10,
    shop_theme = 11,
    shop_scene = 12,
    shop_table = 13,
    shop_music = 14,
    new_comer = 15,    -- 破冰礼包
    gift_exchange = 16,     -- 兑换商城-礼物碎片
    rank_exchange = 17,     -- 兑换商城-扑克总会奖章
    shop_effect = 18,
    activity_gifts = 19,    -- 礼包商城-活动礼包
    hot_spring = 10001,    -- 温泉季商店
    gala_season = 10002,   -- 礼服季商店
}

SHOP_PAGE_TYPE = {
    SIDE = 1,   -- 侧边栏页签
    TOP = 2,    -- 顶部页签
}

SHOP_LIMIT_TYPE = {
    DAILY = 1,      -- 每日限购
    WEEKLY = 2,     -- 每周限购
    MONTHLY = 3,    -- 每月限购
    PERMANENT = 4,  -- 永久限购
}

------------------ 玩家类型 ------------------
USER_TYPE = {
    Normal = 0,     -- 普通玩家
    Developer = 1,  -- 开发者
    Streamer = 2,   -- 主播
}

------------------ 好友 ------------------
FRIEND_STATUS = {
    NOT_FRIEND = -1,    -- 不是好友状态
    NORMAL = 1,         -- 好友状态正常，没拉黑 没删除 没被删除
    BLOCKED = 2,        -- 被拉黑
    DELETE = 3,         -- 主动删除对方
    DELETED = 4,        -- 被对方删除
    APPLY = 5,          -- 好友申请中
    REMOVE = 6,         -- 申请移除
    SEND_APPLY = 7,     -- 发送请求
}

FRIEND_LIST_TYPE = {
    FRIENDS = 1,        -- 好友列表
    APPLY = 2,          -- 申请列表
    BLOCKED = 3,        -- 黑名单列表
}

------------------ 角色 ------------------
-- 皮肤类型
SKIN_KIND = {
    NORMAL = 0, -- 普通
    AWAKEN = 1, -- 觉醒
    PAY = 2,    -- 付费
}

-- 皮肤等级
SKIN_RANK = {
    NONE = 0,   -- 无等级
    SR = 1,  -- SR
    SSR = 2, -- SSR
}

-- 角色语音
ROLE_VOICE = {
    -- 局内
    fold = {"2001_1", "2001_2"},
    ante = "2009",
    sb = "2007",
    bb = "2008",
    check = "2002",
    call = "2003",
    raise = "2005",
    reRaise = "2010",
    bet = "2004",
    all_in = {"2011_1","2011_2"},
    all_in_awakened = {"2011_1","2011_2","2011_3"},
    pot = "2006",
    scrap = "3006",    -- 爆衣

    greeting = "4001",  -- 问候	greeting
    praise = "4002",  -- 称赞	praise
    thanks = "4003",  -- 感谢	thanks
    sorry = "4004",    -- 抱歉	sorry
    surprise = "4005",  -- 震惊	surprise
    sarcasm = "4006",    -- 嘲讽	sarcasm
    urging = "4007",  -- 催促	urging

    take_a_seat = "3001_1",    -- 落座	take_a_seat
    take_a_seat_awakened = "3001_2",   -- 落座_觉醒后 take_a_seat_awakened
    game_starts = "3002",    -- 游戏开始	game_starts
    dealer_turn = "3003",    -- 轮到庄位	dealer_turn
    strong_cards = "3004",  -- 初始牌牌力很强	strong_cards
    weak_cards = "3005",  -- 初始牌牌力很弱	weak_cards
    win_original = "3011_1",  -- 终局获胜_原皮	win_original
    win_awakened = "3011_2",    -- 终局获胜_觉醒皮肤	win_awakened
    -- win = "8023",    -- 获胜
    win = "3009",
    win2 = "3008",

    high_card = "1001",
    one_pair = "1002",
    two_pairs = "1003",
    three_of_a_kind = "1004",
    straight = "1005",
    flush = "1006",
    full_house = "1007",
    four_of_a_kind = "1008",
    straight_flush = "1009",
    royal_flush = "1010",

    -- 局外
}

------------------ 任务 ------------------
TaskStatus = {
    InProgress = 1,     -- 进行中
    Completed = 2,      -- 已完成（未领取）
    Received = 3,       -- 已领取
}

TaskCate = {
    Daily = 1,          -- 日常任务
    Weekly = 2,         -- 周常任务
    SevenDay = 3,       -- 七日任务
    HotSpring = 4,      -- 温泉季任务
    GalaSeason = 4,     -- 礼服季任务
    Festival = 5,       -- 节日任务
    Challenge = 6,      -- 挑战任务
}

TaskType = {
    CheckView = 302,     -- 查看界面
    RoleInteraction = 303,      -- 大厅角色交互
    ClaimDailyFree = 306,       -- 领取每日免费筹码
    PreviewDirection = 307,     -- 背包预览装饰
}

TaskTargetId = {
    ShopChip = 101,         -- 商城-充值筹码界面
    ShopPackage = 102,      -- 商城-特惠礼包界面
    Role = 201,             -- 角色界面
    Info = 301,             -- 其他玩家个人信息界面
    InfoInGame = 302,       -- 牌局其他玩家个人信息界面
    InfoAvatarList = 303,   -- 玩家个人信息头像列表
    TableChat = 304,        -- 牌桌使用快捷语/表情
    Gacha = 401,            -- 抽卡界面
    HandExplanation = 501,  -- 牌型说明界面
    CardDeck = 601,         -- 牌谱界面
    Tournament = 701,       -- 赛事界面
    HotSpring = 10001,      -- 温泉季界面
    GalaSeason = 10002,     -- 礼服季界面
    School = 10003,         -- 开学季界面
    BunnyGirl = 10004,      -- 兔女郎界面

    SpringFestivalMain = 20001, -- 春节活动主界面
    SpringFestivalShop = 20002, -- 春节活动礼包界面

    ThemeActivity = 20001,  -- 主题活动
    
}

TaskTableChatType = {
    Text = 1,
    Emoji = 2,
}

-- 七日任务列表
SevenDayTaskStatus = {
    Running = 1,     -- 当天章节进行中
    Rewarded = 2,   -- 当天章节奖励已领取
    Completed = 3,  -- 全部章节奖励已领取
    Upload = 4,     -- 认证证书已上传
}

-- 七日任务章节状态
SevenDayChapterStatus = {
    Running = 1,    -- 进行中
    Completed = 2,  -- 已完成
    Locked = 3,     -- 未解锁（前置任务未解锁）
    UnReach = 4,    -- 未到开放时间
}

------------------ 引导 ------------------
GuideKind = {
    Story = 1,  -- 播放剧情
    UI = 2,     -- ui 引导
    Draw = 3,   -- 抽卡动画
}

------------------ 活动 ------------------
ActivityType = {
    Normal = 1,     -- 普通活动
    TimeLimit = 2,  -- 限时活动
}

ActivityId = {
    NewmanCheckin = 2001,      -- 新市民七日签到
    ActivitySignIn = 2001,      -- 活动签到

    SevenSignIn = 1001,     -- 七日签到
    SocialMedia = 1002,     -- 关注社媒
    LinkEmail = 1003,       -- 绑定邮箱

    Theme = 10000,         -- 主题活动，包含了下面的活动
    HotSpring = 10001,    -- 温泉季活动
    GalaSeason = 10002,     -- 礼服季活动
    School = 10003,         --开学季活动
    BunnyGirl = 10004,      --兔女郎活动

    SpringFestival = 3001,  --春节活动
}

ActivityCheckInStatus = {
    NoReward = 1,       -- 签到未领取奖励
    Rewaraded = 2,      -- 签到已领取奖励
    NotReach = 0,       -- 未签到
}

MediaPlatform = {
    Facebook = 1,
    Line = 2,
    Discord = 3,
    X = 4,
    Bilili = 5,
    Weibo = 6,
    QQ = 7,
}

------------------ 装饰方案 ------------------
MusicTag = {
    Single = 1,
    Order = 2,
    Random = 3,
}

SchemeRandomTag = {
    NoRandom = 0,
    Random = 1,
}

------------------ 排行榜 ------------------

RankingType = {
    CurWeek = 1,
    LastWeek = 2,
}

------------------ 震动 ------------------
VibrateKind = {
    UI = 1,
    InGame = 2,
    OutGame = 3,
}

------------------ 比赛 ------------------
TOUR_STATUS = {
    Unregister = 0, -- 未报名
    Register = 1,   -- 已报名未开赛
    Inprocess = 2,  -- 比赛进行中
    Finished = 3,   -- 比赛结束
    Losed = 4,      -- 比赛中途被淘汰
}