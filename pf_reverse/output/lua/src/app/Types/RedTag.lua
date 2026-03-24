-- 红点标志树形结构定义
-- 使用 RedManager:bind(go, RedTag.Team) 来添加 Team 节点的监听
local TagLinks = 
{
    Friends = {
        ApplyFriends = {},
    },
    Shop = {
        Recommend = {"FirstRecharge"},
        Recharge = {"DailyFree"},
        ShopVip = {"VipClaimNum"},
    },
    ShopNew = {
        DecorateNew = {},
        SkinNew = {}
    },
    ShopNewOut = {},
    Email = {
        EmailNormal = {"NormalNewEmail"},
        EmailSpecial = {"SpecialNewEmail"},
    },
    Notice = {
        "NoticeActivity", "NoticeSystem",
    },
    Task = {
        DailyTask = {
            DailyPoint = {},
            DailyReward = {},
        },
        WeeklyTask = {
            WeeklyPoint = {},
            WeeklyReward = {},
        },
    },
    Backpack = {    -- 背包
        BackPackProp = {},
        BackPackGift = {},
        BackPackAwaken = {},
        BackpackDecorate = {    -- 装饰
            "BackpackCardFace",
            "BackpackCardBack",
            "BackpackTable",
            "BackpackMusic",
            "BackpackScene",
            "BackpackEff",
        }
    },
    SevenDayTask = {
        TaskChapter = {
            TaskChapterTag = {},
        },
        Sign = {},
    },
    Activity = {    -- 活动
        "ActivitySignIn",
        "ActivityNewmanCheckin",
    },
    SideGame = {
        "Pinball",
    },

    ------------------ 角色 ------------------
    Character = {   -- 角色
        CharacterMain = {},     -- 主界面
    },
    -- 子页签的红点依赖于是否选中了对应的角色
    CharacterProfile = {},  -- 分析
    CharacterProfileVoices = {}, -- 分析 声音
    CharacterProfileVoices1 = {}, -- 分析 声音 tag 1
    CharacterProfileVoices2 = {}, -- 分析 声音 tag 2
    CharacterProfileVoices3 = {}, -- 分析 声音 tag 3
    CharacterProfileVoices4 = {}, -- 分析 声音 tag 4
    CharacterProfileVoices5 = {}, -- 分析 声音 tag 5
    CharacterProfileFiles = {},   -- 分析 档案

    CharacterGarments = {}, -- 衣橱
    CharacterBonds = {},    -- 养成

    ------------------ 活动 温泉季 ------------------
    HotSpring = {
        HotSpringPlot = {},    -- 剧情奖励
        HotSpringTask = {},    -- 任务奖励
    },
    ------------------ 活动 礼服季 ------------------
    GalaSeason = {
        GalaSeasonPlot = {},    -- 剧情解锁
        GalaSeasonTask = {},    -- 任务奖励
    },
    ------------------ 活动 开学季 ------------------
    School = {
        SchoolPlot = {},    -- 剧情解锁
        SchoolTask = {},    -- 任务奖励
    },

    ------------------ 活动 新春 ------------------
    SpringFestival = {
        SpringFestivalRedPacket = {},    -- 红包
        SpringFestivalTask = {},    -- 任务奖励
    },
    ------------------ 更新提示 ------------------
    UpdateTag = {},


}

RedTag = {}
RedTagLink = {}

local function _addRedTag(v, key)
    if RedTagLink[v] then
        print("[BindRedTag] Error 重复的 key", v)
    end
    
    if key and RedTagLink[key] then
        if "table" == type(RedTagLink[key]) then
            local tbr = clone(RedTagLink[key])
            table.insert(tbr, v)
            RedTagLink[v] = tbr
        else
            RedTagLink[v] = {RedTagLink[key], v}
        end
    else
        RedTagLink[v] = v
    end
end

local function _bindRedTag(tbr, key)
    for k, v in pairs(tbr) do
        if "table" == type(v) then
            _addRedTag(k, key)
            _bindRedTag(v, k)
        else
            _addRedTag(v, key)
        end
    end
end
_bindRedTag(TagLinks)
for k, v in pairs(RedTagLink) do
    RedTag[k] = k
