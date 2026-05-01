require("app.EnumConfig")

Config = {
    IS_HIGH_MEMORY = false, -- 是否高内存手机
    IS_LOW_MEMORY = false,  -- 是否低内存手机

    NET_SYNC_TIME = 10,      -- 上报数据间隔时长

    UI_OFFSET_TOP = 0,
    UI_OFFSET_BOTTOM = 0,
    UI_OFFSET_LEFT = 0,
    UI_OFFSET_RIGHT = 0,
    
    -- 前后端数值比例
    SERVER_CLIENT_RATIO = 1,

    -- 方向
    DIR_UP = 1,
    DIR_RIGHT = 2,
    DIR_DOWN = 3,
    DIR_LEFT = 4,

    -- pc 版屏幕分辨率列表
    Resolutions = {
        {1600, 900},
        {1920, 1080},
        {1680, 1050},
        {1600, 1024},
        {1440, 1080},
        {1366, 768},
        {1360, 768},
        {1280, 1024},
        {1280, 960},
        {1280, 800},
        {1280, 768},
        {1280, 720},
        {1176, 664},
        {1152, 864},
        {1024, 768},
        {800, 600},
        {3840, 2160},
        {2560, 1440},
        {2048, 1080},
        {1920, 1440},
        {1920, 1200},
    },

    FrameRates = {60, 120}, -- 帧率列表
    Languages = {"jp", "en", "tw", "zh", "ko"},       -- 多语言列表

    LoginType = {
        RDKEY		= 0,
        GUEST		= 1,
        FACEBOOK	= 3,
        KKACCOUNT	= 4,
        APPLE 		= 6,
        EMAIL 		= 7,
        GOOGLE      = 8,
        TWITTER     = 9,
    },
    
    LoginSys = {
        GUEST		= "guest",
        FACEBOOK	= "facebook",
        KKACCOUNT	= "kkaccount",
        APPLE 		= "apple",
        EMAIL 		= "email",
        TWITTER     = "twitter",
    },
    
	-- Card
	CARD_NUM_2_STRING = {'', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'j', 'q', 'k', 'a'},
	CARD_COLOR_2_STRING = {'d', 'c', 'h', 's'}, --方块 梅花  红桃  黑桃
	JOKER_CARD = 0x0503,

    CARD_SCALE_DEAL = bee.v3(0.3, 0.3, 0.3),    -- 发牌起始大小
    CARD_SCALE_TO_HAND = bee.v3(0.68, 0.68, 0.68),      -- 发牌到手上目标大小
    CARD_SCALE_TO = bee.v3(0.25, 0.25, 0.25),      -- 发牌到桌上目标大小
    CARD_SCALE_BET = bee.v3(0.6, 0.6, 0.6),     -- bet 动画起始大小

    CARD_SCALE_LOSE = bee.v3(0.8, 0.8, 0.6),    -- omaha 手牌不上桌的显示大小

    CARD_ROTATE_180 = bee.v3(0, 0, 360),        -- 发牌旋转角度
    CARD_ROTATE_HANDS = {bee.v3(0, 0, 364), bee.v3(0, 0, 349)}, -- 发到手牌的旋转角度
    CARD_ROTATE_HANDS_OMAHA = {bee.v3(0, 0, 368), bee.v3(0, 0, 364), bee.v3(0, 0, 356), bee.v3(0, 0, 352)}, -- oma 发到手牌的旋转角度

    ROLE_ACTION_SCALE = bee.v3(1.2, 1.2, 1.2),  -- 轮到角色行动时放大
    ROLE_OTHER_SCALE = bee.v3(1, 1, 1), -- 其它角色的 spine 显示缩放

    AWAKEN_LEVEL = 5,   -- 觉醒等级

    -- ui 层级
    UI_LAYER_BALL = 6,
    UI_LAYER_BALL_FLY = 7,

    NO_WRAP_SPACE = " ", -- 不换行的空格
}

DESIGN_WIDTH, DESIGN_HEIGHT = 1920, 1080
DESIGN_WIDTH2, DESIGN_HEIGHT2 = DESIGN_WIDTH / 2, DESIGN_HEIGHT / 2
SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
SCREEN_WIDTH_SAFE, SCREEN_HEIGHT_SAFE = SCREEN_WIDTH, SCREEN_HEIGHT

function refreshScreenSize()
    SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
    local w, h, s = 2020, 1080, CU.Screen.height / CU.Screen.width
    if s >= SCREEN_HEIGHT / SCREEN_WIDTH then
        SCREEN_HEIGHT = s * SCREEN_WIDTH
        UiManager:setScreenMatchValue(0)
    else
        UiManager:setScreenMatchValue(1)
        SCREEN_WIDTH = SCREEN_HEIGHT / s
    end
    SCREEN_WIDTH_SAFE, SCREEN_HEIGHT_SAFE = SCREEN_WIDTH, SCREEN_HEIGHT
    
    Config.UI_OFFSET_LEFT = 0
    Config.UI_OFFSET_RIGHT = 0
    if SCREEN_WIDTH > 2800 then
        Config.UI_OFFSET_LEFT = (2800 - SCREEN_WIDTH) / 2
        SCREEN_WIDTH = 2800
        SCREEN_WIDTH_SAFE = SCREEN_WIDTH
        if bee.isPc and not bee.isEditor then
        else
            Config.UI_OFFSET_LEFT = Config.UI_OFFSET_LEFT - 80
            SCREEN_WIDTH_SAFE = SCREEN_WIDTH
        end
        Config.UI_OFFSET_RIGHT = -Config.UI_OFFSET_LEFT
        SCREEN_WIDTH_SAFE = SCREEN_WIDTH - 160
    elseif s < h / w then
        if bee.isPc and not bee.isEditor then
        else
            Config.UI_OFFSET_LEFT = -80
            Config.UI_OFFSET_RIGHT = -Config.UI_OFFSET_LEFT
            SCREEN_WIDTH_SAFE = SCREEN_WIDTH - 160
        end
    end
    if SCREEN_HEIGHT > 1440 then
        Config.UI_OFFSET_TOP = (1440 - SCREEN_HEIGHT) / 2
        Config.UI_OFFSET_BOTTOM = -Config.UI_OFFSET_TOP
    else
        Config.UI_OFFSET_TOP = 0
        Config.UI_OFFSET_BOTTOM = 0
    end

    UiBase:__setAdapt(Config.UI_OFFSET_TOP, Config.UI_OFFSET_BOTTOM, Config.UI_OFFSET_LEFT, Config.UI_OFFSET_RIGHT)
end

refreshScreenSize()
-- bee.once(0.2, function()
--     refreshScreenSize()
-- end)

if DT then
    DT.DOTween.SetTweensCapacity(500, 250);
end

bee.isLongScreen = SCREEN_WIDTH / SCREEN_HEIGHT > 1.78

bee.on("evt_onScreenChanged", function()
    refreshScreenSize()
    UiManager:resetScreenMatch()
    local uis = UiManager:getUiStack()
    if uis then
        for _, ui in ipairs(uis) do
            if ui.cls and ui.cls.onAdapt then
                ui.cls:onAdapt()
            end
        end
    end
end)