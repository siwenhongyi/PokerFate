local P = class("VIPExclusiveAssistant", UiDialog)

-- 专属奖励道具
local TITLE_ID = 20400009          -- 专属称号
local AVATAR_FRAME_ID = 20200014   -- 专属头像框

-- 助手平台按钮，key 为 tpl_vip_assistant_platform_info 的配置 id
-- 1 Discord / 2 QQ / 3 Line / 4 Line
local PLATFORM_BUTTONS = {
    [1] = { node = "BgBts/DiscordButton", image = "shop_vip_assistant_sns_button_02" },
    [2] = { node = "BgBts/QQButton", image = "shop_vip_assistant_sns_button_03" },
    [3] = { node = "BgBts/LineButton", image = "shop_vip_assistant_sns_button_01" },
    [4] = { node = "BgBts/LineButton", image = "shop_vip_assistant_sns_button_01" },
}

-- Unity 的 Application.OpenURL 需要完整 URL（带协议），
-- 如 "discordapp.com/users/xxx" 这种缺协议的需补上 https:// 才能直接打开
local function fixLink(link)
    if not link or link == "" then
        return nil
    end
    if not string.match(link, "^%a[%w+.-]*:") then
        link = "https://" .. link
    end
    return link
end

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Reward = self:find("Reward", self.Center)
    self.SNS = self:find("SNS", self.Center)
    self.Title = self:find("Title", self.Center)
    self.BgTips = self:find("BgTips", self.Center)
    self.TextVipTip = self:find("Character/TextVipTip", self.Center)

    -- Item01 专属名称显示（玩家名片）
    self.Player = self:find("Player", self:find("Item01", self.Reward))
    self.TextName = self:find("TextName", self.Player)
    self.TextChip = self:find("TextChip", self.Player)
    self.ImageLevel = self:find("icon_level_01", self.Player)

    -- Item02 专属称号 / Item03 专属头像框
    self.ImageTitle = self:find("avatartitle_ranking_03", self:find("Item02", self.Reward))
    self.ImageFrame = self:find("avatarframe_common_08", self:find("Item03", self.Reward))

    -- Item04 任选服饰 / Item05 月度福利
    self.Item04 = self:find("Item04", self.Reward)
    self.Item05 = self:find("Item05", self.Reward)
    self.ImageChip = self:find("Main/shop_vip_assistant_reward_icon_chip", self.Item05)
    self.InfoButton = self:find("Information/InfoButton", self.Item05)

    -- 助手联系方式按钮
    self.SNSButtons = {}
    for id, cfg in pairs(PLATFORM_BUTTONS) do
        local node = self:find(cfg.node, self.SNS)
        self.SNSButtons[id] = {
            node = node,
            image = self:find(cfg.image, node),
        }
    end

    -- 月度福利列表
    self.TipsView = self:find("Tips/View", self.BgTips)
    self.TipsItem = self:find("Item", self.TipsView)
    self.TipsItem:SetActive(false)
    self._tipItems = {}

    bee.addClick(self:find("CloseButton", self.Center), function()
        self:hideUI()
    end)

    -- 服饰福利说明按钮
    bee.addClick(self:find("Information/InfoButton", self.Item04), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipUD", {
            text = _T("LAB_VIP_ASSISTANT_11"),
            target = self:find("Information/InfoButton", self.Item04),
        })
    end)
    -- 月度福利说明按钮
    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        self:refreshMonthlyReward()
        self.BgTips:SetActive(not self.BgTips.activeSelf)
        bee.logEvent("vip-assistant-monthly-tips")
    end)
    -- 点击月度福利说明面板收起
    bee.addClick(self.BgTips, function()
        Game:playSound("ui_button_confirm")
        self.BgTips:SetActive(false)
    end)

    -- 点击奖励图标弹出对应道具提示
    self:bindItemTip(self.ImageTitle, TITLE_ID)
    self:bindItemTip(self.ImageFrame, AVATAR_FRAME_ID)
    self:bindItemTip(self.ImageChip, GPropId.Gold)

    self.BgTips:SetActive(false)
end

-- 点击节点弹出道具提示
function P:bindItemTip(node, id)
    bee.addClick(node, function()
        Game:playSound("ui_button_confirm")
        local itemId = type(id) == "function" and id() or id
        if itemId then
            UiManager:showUI("CommonItemTip", { data = ItemModel:getItem(itemId, true), target = node })
        end
    end)
end

function P:onShow()
    self.BgTips:SetActive(false)
    self:refreshTitle()
    self:refreshTextVipTip()
    self:refreshPlayer()
    self:refreshReward()
    self:refreshSNS()

    bee.logEvent("vip-assistant-view")

    self:find("Bg/ImageCertified", self.Center):SetActive(SettingModel:isHasVipHelper())
end

-- TextVipTip 只有英文需要 bestFit 自适应字号，其它语言关掉，避免字号被缩得过小
function P:refreshTextVipTip()
    if bee.isNull(self.TextVipTip) then
        return
    end
    local text = self.TextVipTip:GetComponent("Text")
    if bee.isNull(text) then
        return
    end
    text.resizeTextForBestFit = LAN:getLanguage() == "en" or LAN:getLanguage() == "jp"
end

-- 标题图只显示当前语言
function P:refreshTitle()
    local lan = LAN:getLanguage()
    local show = false
    for _, name in ipairs({ "zh", "tw", "en", "jp" }) do
        local node = self:find(name, self.Title)
        if node then
            local active = name == lan
            node:SetActive(active)
            show = show or active
        end
    end
    if not show then
        local node = self:find("en", self.Title)
        if node then
            node:SetActive(true)
        end
    end
end

function P:refreshPlayer()
    GF.setPlayerName(self.TextName, PlayerModel:getName(), 2, 164)
    bee.setText(self.TextChip, _N2(PlayerModel:getGold()))
    local levelCfg = tpl_level[PlayerModel:getCurLevel()]
    if levelCfg then
        bee.setIcon(self.ImageLevel, levelCfg.icon)
    end
end

function P:refreshReward()
    -- 图标都取配置表图标
    GF.setTitleImage(self.ImageTitle, TITLE_ID)
    GF.setFrameImage(self.ImageFrame, AVATAR_FRAME_ID)
end

-- 按当前语言从助手平台配置中取出要显示的按钮
function P:refreshSNS()
    for _, v in pairs(self.SNSButtons) do
        v.node:SetActive(false)
    end

    local curCfg
    for _, v in ipairs(tpl_vip_assistant_platform_list) do
        if v.lang == LAN:getLanguage() then
            curCfg = v
            break
        end
    end
    curCfg = curCfg or tpl_vip_assistant_platform_list[1]
    if not curCfg then
        return
    end

    for _, id in ipairs(curCfg.platform) do
        local info = tpl_vip_assistant_platform_info[id]
        local button = self.SNSButtons[id]
        if info and button then
            button.node:SetActive(true)
            if button.image then
                bee.setIcon(button.image, info.icon)
            end
            bee.addClick(button.node, function()
                Game:playSound("ui_button_confirm")
                bee.logEvent("vip-assistant-path", id)
                if 2 == id then
                    CS.SdkHelper.copyText(info.link)
                    UiManager:showToast(_T("LAB_VIP_ASSISTANT_10"))
                else
                    local link = fixLink(info.link)
                    if link then
                        bee.openUrl(link)
                    end
                end
            end, true)
        end
    end
end

-- 月度福利读取 tpl_vip_level.monthly_rewards 字段
function P:refreshMonthlyReward()
    if self._isInitMonthlyReward then
        return
    end
    self._isInitMonthlyReward = true
    local levelData = tpl_vip_level[VipModel:getVipLevel()]
    local rewards = levelData and levelData.monthly_rewards
    if not rewards then
        for _, v in ipairs(tpl_vip_level_list) do
            if v.monthly_rewards then
                rewards = v.monthly_rewards
                break
            end
        end
    end
    if rewards and tpl_props[rewards[1]] then
        self._monthlyItemId = rewards[1]
    end

    for _, v in pairs(self._tipItems) do
        if not bee.isNull(v) then
            CU.GameObject.Destroy(v)
        end
    end
    self._tipItems = {}

    for k, v in ipairs(tpl_vip_level_list) do
        local rw = v.monthly_rewards
        if rw then
            local item = CU.GameObject.Instantiate(self.TipsItem, self.TipsView.transform, false)
            item:SetActive(true)
            bee.setText(self:find("TextLevel", item), tostring(v.id))
            if tpl_props[rw[1]] then
                bee.setIcon(self:find("icon_10100001", item), tpl_props[rw[1]].icon)
            end
            bee.setTextGold(self:find("TextGold", item), _N2(rw[2]))
            table.insert(self._tipItems, item)

            self:find("pinball_record_tips_frame_01", item):SetActive(k % 2 == 0)
            self:find("pinball_record_tips_frame_02", item):SetActive(k % 2 == 1)
            self:find("pinball_record_list_frame_on", item):SetActive(v.id == VipModel:getVipLevel())
        end
    end
end

return P