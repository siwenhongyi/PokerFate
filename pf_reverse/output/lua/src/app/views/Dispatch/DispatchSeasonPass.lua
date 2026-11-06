-- 派遣赛季通行证
-- 页面包含 3 个页签：通行证 / 经营奖励 / 经营加速中心
-- 目前仅实现「通行证」页签逻辑，其余两个页签保留容器与切换（内容待后续填充）
local P = class("DispatchSeasonPass", UiFullView)

local TabIndex = {
    SeasonPass = 1,   -- 通行证
    Reward     = 2,   -- 经营奖励
    Accelerate = 3,   -- 经营加速中心
}

-- 页签内容容器名称（AnimRoot 下）
local TabContentName = {
    [TabIndex.SeasonPass] = "CenterSeasonPass",
    [TabIndex.Reward]     = "CenterRewardCenter",
    [TabIndex.Accelerate] = "CenterBusinessCenter",
}

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    self.RightTop = self:find("RightTop", AnimRoot)
    self.LeftTop = self:find("LeftTop", AnimRoot)

    -- 通用角标
    self.BackButton = self:find("BackButton", self.LeftTop)
    self.RecordButton = self:find("RecordButton", self.RightTop)
    self.CharacterButton = self:find("CharacterButton", self.RightTop)
    self.GoldItem1 = self:find("GoldItem1", self.RightTop)
    self.GoldItem2 = self:find("GoldItem2", self.RightTop)

    self.Time = self:find("Time", AnimRoot)
    self.TextTime = self:find("TextTime", self.Time)

    bee.addClick(self.BackButton, function()
        self:hideUI()
    end)
    bee.addClick(self.RecordButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-history")
        UiManager:showUI("DispatchSideRecord")
    end)
    bee.addClick(self.CharacterButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-my-character")
        UiManager:showUI("DispatchSideCharacter")
    end)

    -- 页签按钮：动态遍历 TabList 子节点，避免依赖具体命名
    self.TabList = self:find("TabList", self.LeftTop)
    self.tabItemList = {
        self:find("Item01", self.TabList),
        self:find("Item02", self.TabList),
        self:find("Item03", self.TabList),
    }
    RedManager:bind(self:find("Reddot", self.tabItemList[1]), RedTag.DispatchSeasonPass)
    RedManager:bind(self:find("Reddot", self.tabItemList[2]), RedTag.DispatchReward)

    -- 页签内容容器
    self.Views = {}
    for i = 1, 3 do
        self.Views[i] = self:find(TabContentName[i], AnimRoot)
    end

    -- 绑定页签点击
    for i, tabItem in ipairs(self.tabItemList) do
        bee.onCheck(tabItem, function(isOn)
            if isOn and not self._watiStart then
                if i == 1 then
                    bee.logEvent("dispatch-up-passcard")
                elseif i == 2 then
                    bee.logEvent("dispatch-up-rewards")
                elseif i == 3 then
                    bee.logEvent("dispatch-up-shop")
                end
                self:onClickTab(i)
            end
        end)
    end

    self._data = DispatchModel:getPassInfo()
    -- 通行证页 UI 节点
    self:initSeasonPassNodes()
end

function P:onShow()
    DispatchModel:reqPassInfo(nil)

    bee.invoke(self.GoldItem1, "setItemId", GPropId.CampDispatchUpgrade)
    bee.invoke(self.GoldItem2, "setItemId", GPropId.AccelerateDispatch)
    self:evt_ItemChangeRSP()

    self:schedule(1, function()
        self:refreshSeasonPassTime()
    end)

    local idx = self._params and self._params.index or 1
    if self._params and self._params.jump and self._params.jump.sub_page then
        idx = self._params.jump.sub_page[1]
    end
    self:onClickTab(idx or 1)
    bee.setCheck(self.tabItemList[idx or 1])
end

-- 点击页签
function P:onClickTab(index)
    if index == self._curTab then
        return
    end
    Game:playSound("ui_tab_switch_1")
    self._curTab = index
    for k, v in ipairs(self.Views) do
        v:SetActive(k == index)
    end
end

--------------------------------------------------------------------------------
-- 通行证页
--------------------------------------------------------------------------------
function P:initSeasonPassNodes()
    local root = self.Views[TabIndex.SeasonPass]
    if not root then
        return
    end

    local SeasonPassMain = self:find("SeasonPassMain", root)
    local Title = self:find("Title", SeasonPassMain)

    -- 等级
    self.TextCount1 = self:find("Experience/TextCount2/TextCount1", Title)
    self.TextCount2 = self:find("Experience/TextCount2", Title)
    self.TextMax = self:find("Experience/TextMax", Title)
    self.Text01 = self:find("Text01", Title)
    self.Text02 = self:find("Text02", Title)
    self.Maxlevel = self:find("Maxlevel", Title)

    -- 经验 / 时间
    self.ScheduleSlider = self:find("Experience/ScheduleSlider", Title)

    -- 解锁高级通行证
    self.UnlockPass = self:find("UnlockPass", root)
    self.UnlockButton = self:find("UnlockButton", self.UnlockPass)
    self.TextPrice = self:find("UnlockButton/TextPrice", self.UnlockButton)
    self.Unlocked = self:find("Unlocked", self.UnlockPass)

    -- 领取奖励
    self.ClaimReward = self:find("ClaimReward", root)
    self.ClaimButton = self:find("ClaimButton", self.ClaimReward)
    self.ReceivedButton = self:find("ReceivedButton", self.ClaimReward)
    self.NoRewardButton = self:find("NoRewardButton", self.ClaimReward)

    -- 奖励列表（UiListEx 数据绑定，数据源 tpl_passcard_info_list）
    local Reward = self:find("Reward", SeasonPassMain)
    local RewardList = self:find("RewardList", Reward)
    local RewardItem = self:find("Item", RewardList)
    RewardItem:SetActive(false)

    self.Premium = self:find("RewardTitle/Premium/dispatch_seasonpass_main_reward_title_icon_02", Reward)
    self.UnlockedIcon = self:find("RewardTitle/Premium/Unlocked", Reward)

    self.rewardList = UiListEx:create(RewardList)
    self.rewardList:setCreateFunc(function()
        return CU.GameObject.Instantiate(RewardItem)
    end)
    self.rewardList:setRefreshFunc(function(data, item, isInit, index)
        self:setRewardItem(item, data, index)
    end)
    self.rewardList:setWidth(215)
    self.rewardList:setDatas(tpl_passcard_info_list)

    local yIndex = self._data.level
    for i = 1, self._data.level do
        if table.indexof(self._data.ordinary, i) < 0 or (self._data.has_pass_card and table.indexof(self._data.advanced, i) < 0) then
            yIndex = i
            break
        end
    end
    if yIndex > 0 then
        self.rewardList:moveToYItem(yIndex)
    end

    -- 解锁高级通行证
    bee.addClick(self:find("UnlockButton", self.UnlockButton), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-up-passcard-buy")
        ShopModel:pay(tpl_shop_passcard[1])
    end)

    -- 领取当前奖励
    bee.addClick(self.ClaimButton, function()
        Game:playSound("ui_button_confirm")
        if not bee.checkCd("Dispatch_reqPassReward", 2) then
            return
        end
        DispatchModel:reqPassReward(1, true, true, function()
            self:refreshSeasonPass()
            self.rewardList:refreshShowingUi()
        end)
    end)

    bee.addClick(self.NoRewardButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
    end)

    local InfoButton = self:find("Experience/TEXT/InfoButton", Title)
    bee.addClick(InfoButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipRLWhite", {text = _T("LAB_DISPATCH_94"), target = InfoButton})
    end)

    local TipItem = self:find("Item", Title)
    bee.addClick(TipItem, function()
        Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = {id = GPropId.CampDispatchUpgrade, num = 1}, target = TipItem})
    end)

    self:refreshSeasonPass()
end

function P:refreshSeasonPassTime()
    local dt = tpl_constdata.Dispatch_End - bee.getServerTime()
    if dt <= 0 then
        self.Time:SetActive(false)
    else
        bee.setText(self.TextTime, TimeHelp:getTimeLeftStr(dt))
    end
end

-- 刷新单个奖励 item
function P:setRewardItem(item, data, index)
    -- 普通奖励
    self:setRewardSlot(self:find("Item01", item), data.ordinary_rewards, data, false)
    -- 高级奖励
    self:setRewardSlot(self:find("Item02", item), data.advanced_rewards, data, true)

    local ItemNum = self:find("ItemNum", item)
    local Normal = self:find("Normal", ItemNum)
    local Received = self:find("Received", ItemNum)
    local Claim = self:find("Claim", ItemNum)

    local hasReward = data.level <= self._data.level
    local isClaim = hasReward and table.indexof(self._data.ordinary, data.level) > 0
    if isClaim and self._data.has_pass_card then
        isClaim = table.indexof(self._data.advanced, data.level) > 0
    end

    Normal:SetActive(not hasReward)
    Received:SetActive(hasReward)
    Claim:SetActive(hasReward and not isClaim)

    bee.setText(self:find("TextNum", Normal), string.format("%d", data.level))
    bee.setText(self:find("TextNum", Received), string.format("%d", data.level))
    bee.setText(self:find("TextNum", Claim), string.format("%d", data.level))

    local RankSlider1 = self:find("RankSlider1", item)
    local RankSlider2 = self:find("RankSlider2", item)
    RankSlider1:SetActive(data.level == #tpl_passcard_info_list)
    RankSlider2:SetActive(data.level ~= #tpl_passcard_info_list)
end

-- 在单个奖励格子里渲染道具
function P:setRewardSlot(slot, reward, data, isAdvanced)
    PropItem:create(self:find("Item", slot), {id = reward[1], num = reward[2]}):bindTips()

    local hasReward = data.level <= self._data.level and (not isAdvanced or self._data.has_pass_card)
    local isClaim = hasReward and table.indexof(isAdvanced and self._data.advanced or self._data.ordinary, data.level) > 0

    -- self:find("Lock", slot):SetActive(not hasReward)
    self:find("Lock", slot):SetActive(not self._data.has_pass_card)
    self:find("Received", slot):SetActive(hasReward and isClaim)
    self:find("Light", slot):SetActive(data.level == #tpl_passcard_info_list or data.level == self._data.level + 1)
    self:find("Reddot", slot):SetActive(hasReward and not isClaim)

    if hasReward and not isClaim then
        bee.addClick(self:find("Reddot", slot), function()
            Game:playSound("ui_button_confirm")
            if not bee.checkCd("Dispatch_reqPassReward", 2) then
                return
            end
            DispatchModel:reqPassReward(data.level, isAdvanced, false, function()
                self:refreshSeasonPass()
                self.rewardList:refreshShowingUi()
            end)
        end, true)
    end
end

function P:refreshSeasonPass()
    bee.setText(self:find("TextLevel", self.Text01), string.format("%d", self._data.level))
    if self._data.level + 1 < #tpl_passcard_info_list then
        bee.setText(self:find("TextLevel", self.Text02), string.format("%d", self._data.level + 1))
        self.Maxlevel:SetActive(false)

        bee.setText(self.TextCount1, _N(self._data.item_num))
        bee.setText(self.TextCount2, "/" .. _N(tpl_passcard_info[self._data.level + 1].level_up_cost))
        self.TextMax:SetActive(false)

        bee.setSliderValue(self.ScheduleSlider, self._data.item_num / tpl_passcard_info[self._data.level + 1].level_up_cost)
    else
        self.Text02:SetActive(false)
        self.Maxlevel:SetActive(true)

        self.TextCount1:SetActive(false)
        self.TextCount2:SetActive(false)
        bee.setText(self.TextMax, _N(tpl_passcard_info[self._data.level].level_up_cost) .. "/" .. _N(tpl_passcard_info[self._data.level].level_up_cost))
        self.TextMax:SetActive(true)

        bee.setSliderValue(self.ScheduleSlider, 1)
    end
    
    local pidCfg = ShopModel:getPidData(tpl_constdata.Dispatch_Passcard)
    bee.setText(self.TextPrice, ShopModel:getPriText(pidCfg))
    
    self.UnlockButton:SetActive(not self._data.has_pass_card)
    self.Unlocked:SetActive(self._data.has_pass_card)
    self.UnlockedIcon:SetActive(not self._data.has_pass_card)

    local hasReward = false
    for i = 0, self._data.level do
        if table.indexof(self._data.ordinary, i) < 0 or (self._data.has_pass_card and table.indexof(self._data.advanced, i) < 0) then
            hasReward = true
            break
        end
    end
    self.ClaimButton:SetActive(hasReward)
    self.ReceivedButton:SetActive(not hasReward and self._data.level == #tpl_passcard_info_list)
    self.NoRewardButton:SetActive(not hasReward and self._data.level < #tpl_passcard_info_list)

    self:refreshSeasonPassTime()
end

--------------------------------------------------------------------------------
-- 经营奖励 / 经营加速中心（待实现）
--------------------------------------------------------------------------------
-- function P:refreshReward() end
-- function P:refreshAccelerate() end

--------------------------------------------------------------------------------
-- 事件处理
--------------------------------------------------------------------------------
function P:evt_ItemChangeRSP()
    bee.invoke(self.GoldItem1, "setCount", _N(ItemModel:getItemNumById(GPropId.CampDispatchUpgrade)))
    bee.invoke(self.GoldItem2, "setCount", _N(ItemModel:getItemNumById(GPropId.AccelerateDispatch)))
end

function P:evt_passCardData()
    self:refreshSeasonPass()
end

function P:evt_pay_sucess(data)
    if data and data.pidData and data.pidData.buy_id == tpl_constdata.Dispatch_Passcard then
        self:once(0.2, function()
            self:refreshSeasonPass()
            self.rewardList:refreshShowingUi()
            AnimationMgr:playUIEffect("Prefab/Dispatch/Eff_poker_Ui_DispatchStar_txz_js", self.Premium.transform, bee.v3())
        end)
    end
end

return P