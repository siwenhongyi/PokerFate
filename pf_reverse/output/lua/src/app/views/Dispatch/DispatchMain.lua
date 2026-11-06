local P = class("DispatchMain", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", self.AnimRoot)
    local Left = self:find("Left", self.AnimRoot)
    local LeftBottom = self:find("LeftBottom", self.AnimRoot)
    local RightTop = self:find("RightTop", self.AnimRoot)
    local LeftTop = self:find("LeftTop", self.AnimRoot)

    -- 事务所列表
    self.TabListObj = self:find("TabList", Left)
    self.ItemTab = self:find("ItemTab", self.TabListObj)
    self.ItemTab:SetActive(false)

    -- 事务列表
    local Affair = self:find("Affair", Center)
    local AffairFrame = self:find("AffairFrame", Affair)
    self.TopFrameBg1 = self:find("TopFrameBg1", AffairFrame)
    self.TopFrameBg2 = self:find("TopFrameBg2", AffairFrame)
    self.AffairNameText = self:find("AffairNameText", AffairFrame)
    self.ImproveButton = self:find("ImproveButton", AffairFrame)
    self.Quantity = self:find("Quantity", AffairFrame)
    self.QuantityIcon = self:find("QuantityIcon", self.Quantity)
    self.QuantityText = self:find("QuantityText", self.Quantity)
    self.CampMax = self:find("CampMax", AffairFrame)
    self.AffairListObj = self:find("AffairList", Affair)
    self.ItemAffair = self:find("ItemAffair", self.AffairListObj)
    self.ItemAffair:SetActive(false)
    self.Refresh = self:find("Refresh", Affair)
    self.RefreshText = self:find("Number/RefreshText", self.Refresh)
    self.FreeRefreshButton = self:find("FreeRefreshButton", self.Refresh)
    self.FreeGrayRefreshButton = self:find("FreeGrayRefreshButton", self.Refresh)
    self.PaidRefreshButton = self:find("PaidRefreshButton", self.Refresh)
    self.PaidGrayRefreshButton = self:find("PaidGrayRefreshButton", self.Refresh)

    -- 事务详情
    self.Detail = self:find("Detail/AnimRoot", Center)
    self.DetailFrame = self:find("DetailFrame", self.Detail)
    self.DetailNameText = self:find("DetailNameText", self.Detail)

    self.Normal = self:find("Normal", self.Detail)
    self.AwardListCont = self:find("Main/Award/AwardList/Viewport/Content", self.Normal)
    self.ExpAwardItem = self:find("ExpAwardItem", self.AwardListCont)
    self.BondAwardItem = self:find("BondAwardItem", self.AwardListCont)
    self.RoleStarAwardItem = self:find("RoleStarAwardItem", self.AwardListCont)
    self.DispatchExpAwardItem = self:find("DispatchExpAwardItem", self.AwardListCont)
    self.RewardBonusAwardItem = self:find("RewardBonusAwardItem", self.AwardListCont)
    self.DetailTimeText = self:find("Main/Time/DetailTimeText", self.Normal)
    self.StarText = self:find("Main/Star/StarText", self.Normal)
    self.RoleText = self:find("Main/Role/RoleText", self.Normal)
    self.Stars = self:find("Main/Star/Stars", self.Normal)
    self.OrdinaryNumText = self:find("Ordinary/OrdinaryNumText", self.Normal)
    self.OrdinaryButton = self:find("Ordinary/OrdinaryButton", self.Normal)
    self.OrdinaryText = self:find("Ordinary/Number/OrdinaryText", self.Normal)
    self.OrdinaryIcon = self:find("Ordinary/OrdinaryButton/Item/OrdinaryIcon", self.Normal)
    self.SeniorButton = self:find("Senior/SeniorButton", self.Normal)
    self.SeniorText = self:find("Senior/Number/SeniorText", self.Normal)
    self.SeniorIcon = self:find("Senior/SeniorButton/Item/SeniorIcon", self.Normal)

    self.Dispatching = self:find("Dispatching", self.Detail)
    self.RoleCampIcon = self:find("RoleCampIcon", self.Dispatching)
    self.StatusText = self:find("Condition/StatusText", self.Dispatching)
    self.RoleCountText = self:find("Condition/Quantity/RoleCountText", self.Dispatching)
    self.CharacterImageRaw = self:find("Character/Area/CharacterImageRaw", self.Dispatching)
    self.EmojiAnim = self:find("Character/EmojiAnim", self.Dispatching)
    self.EmojiAnim:SetActive(false)
    self.Arrow = self:find("Arrow", self.Dispatching)
    self.RightButton = self:find("Arrow/RightButton", self.Dispatching)
    self.LeftButton = self:find("Arrow/LeftButton", self.Dispatching)
    self.BuffList = self:find("BuffList", self.Dispatching)
    self.RewardBonusBuff = self:find("RewardBonusBuff", self.BuffList)
    self.BaseRewardUpBuff = self:find("BaseRewardUpBuff", self.BuffList)
    self.TimeReduceBuff = self:find("TimeReduceBuff", self.BuffList)
    self.DecelerateBuff = self:find("DecelerateBuff", self.BuffList)
    self.RewardListCont = self:find("Bottom/Reward/RewardList/Viewport/Content", self.Dispatching)
    self.ExpRewardItem = self:find("ExpRewardItem", self.RewardListCont)
    self.BondRewardItem = self:find("BondRewardItem", self.RewardListCont)
    self.RoleStarRewardItem = self:find("RoleStarRewardItem", self.RewardListCont)
    self.DispatchExpRewardItem = self:find("DispatchExpRewardItem", self.RewardListCont)
    self.RewardBonusRewardItem = self:find("RewardBonusRewardItem", self.RewardListCont)
    self.RewardItem = self:find("RewardItem", self.RewardListCont)
    self.RewardItem:SetActive(false)
    self.DispatchingTimeText = self:find("Bottom/Time/DispatchingTimeText", self.Dispatching)
    self.CompletedText = self:find("Bottom/Time/CompletedText", self.Dispatching)
    self.AccelerateButton = self:find("Bottom/AccelerateButton", self.Dispatching)
    self.Claim = self:find("Bottom/Claim", self.Dispatching)
    self.ClaimButton = self:find("Bottom/Claim/ClaimButton", self.Dispatching)
    self.SkipPlotToggle = self:find("SkipPlotToggle", self.Claim)

    self.RecordButton = self:find("RecordButton", RightTop)
    self.CharacterButton = self:find("CharacterButton", RightTop)

    self.DispatchShopButton = self:find("DispatchShopButton", LeftBottom)
    RedManager:bind(self:find("Reddot", self.DispatchShopButton), RedTag.DispatchCenter)
    bee.addClick(self.DispatchShopButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-up")
        UiManager:showUI("DispatchSeasonPass")
    end)

    self.GoldItem1 = self:find("GoldItem1", RightTop)
    self.GoldItem2 = self:find("GoldItem2", RightTop)

    self.InfoButton = self:find("InfoButton", LeftTop)
    self.BackButton = self:find("BackButton", LeftTop)
    self.Time = self:find("Time", LeftTop)
    self.TextTime = self:find("Time/TextTime", LeftTop)

    bee.addClick(self.BackButton, function()
        self:hideUI()
    end)
    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-rules")
        UiManager:showUI("DispatchRules")
    end)

    bee.addClick(self.ImproveButton, function()
        Game:playSound("ui_button_confirm")
        DispatchModel:upgradeCamp(self._selectedCamp)
    end)

    bee.addClick(self.FreeRefreshButton, function()
        Game:playSound("ui_button_confirm")
        DispatchModel:checkRefreshCamp(self._selectedCamp, function()
            self._selectedEventId = nil
            self._playAffairItemAnim = true
        end)
    end)
    bee.addClick(self.PaidRefreshButton, function()
        Game:playSound("ui_button_confirm")
        DispatchModel:checkRefreshCamp(self._selectedCamp, function()
            self._selectedEventId = nil
            self._playAffairItemAnim = true
        end)
    end)

    bee.addClick(self.OrdinaryButton, function()
        if not self._selectedEventId then
            return
        end
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-ordinary", self._selectedCamp, self._selectedEventId)
        if DispatchModel:getRemainOrdinaryTimes() <= 0 then
            UiManager:showToast(_T("LAB_DISPATCH_146"))
            return
        end
        if ItemModel:getItemNumById(GPropId.OrdinaryDispatch) <= 0 then
            UiManager:showUI("BackpackDetail", {data = {item_id = GPropId.OrdinaryDispatch, num = ItemModel:getItemNumById(GPropId.OrdinaryDispatch)}})
            UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
            return
        end
        UiManager:showUI("DispatchSelection", {event = self._selectedEventId, item_id = GPropId.OrdinaryDispatch})
    end)
    bee.addClick(self.SeniorButton, function()
        if not self._selectedEventId then
            return
        end
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-advanced", self._selectedCamp, self._selectedEventId)
        if ItemModel:getItemNumById(GPropId.SeniorDispatch) <= 0 then
            UiManager:showUI("BackpackDetail", {data = {item_id = GPropId.SeniorDispatch, num = ItemModel:getItemNumById(GPropId.SeniorDispatch)}})
            UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
            return
        end
        UiManager:showUI("DispatchSelection", {event = self._selectedEventId, item_id = GPropId.SeniorDispatch})
    end)

    bee.addClick(self.CharacterButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-my-character")
        UiManager:showUI("DispatchSideCharacter")
    end)
    bee.addClick(self.RecordButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-history")
        UiManager:showUI("DispatchSideRecord")
    end)

    bee.addClick(self.AccelerateButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("DispatchAccelerate", {event = self._selectedEvent, cb = function()
            self:setAffairList()
            self:setDetailCont()
        end})
    end)
    bee.addClick(self.ClaimButton, function()
        Game:playSound("ui_button_confirm")
        self:onClickClaimReward()
    end)

    bee.addClick(self.LeftButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-event-switch")
        self._selectedIndex = self._selectedIndex - 1
        if self._selectedIndex <= 0 then
            self._selectedIndex = self._maxRoleCount
        end
        self._selectedEvent = nil
        self:setDispatchingDetail()
    end)
    bee.addClick(self.RightButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("dispatch-event-switch")
        self._selectedIndex = self._selectedIndex + 1
        if self._selectedIndex > self._maxRoleCount then
            self._selectedIndex = 1
        end
        self._selectedEvent = nil
        self:setDispatchingDetail()
    end)

    bee.setCheck(self.SkipPlotToggle, true, DispatchModel:getSkipPlot())
    bee.addValueChanged(self.SkipPlotToggle, function(isOn)
        Game:playSound("ui_tab_switch_1")
        DispatchModel:setSkipPlot(isOn)
    end)

    self.LoadingMask = self:find("LoadingMask")
    self.LoadingBackButton = self:find("LoadingBackButton", self.LoadingMask)
    bee.addClick(self.LoadingBackButton, function()
        self:hideUI()
    end)

    bee.addClick(self.FreeGrayRefreshButton, function()
        UiManager:showToast(_T("LAB_DISPATCH_152"))
    end)
    bee.addClick(self.PaidGrayRefreshButton, function()
        UiManager:showToast(_T("LAB_DISPATCH_152"))
    end)

    self.LoadingMask:SetActive(false)
    self.AnimRoot:SetActive(false)

    self._affairTimeTag = {}
end

function P:onStart()
    self._selectedCamp = DispatchModel:getLastCampInt() or 0
    self._selectedIndex = 1
    self._isFirstAnim = true
    self._playAffairItemAnim = true
    self._affairListAnimTag = {}
    self:initTabList()
    self:initAffairList()

    self._isInit = false
    self:schedule(0.2, function()
        if not self._isInit then
            self.LoadingMask:SetActive(true)
        end
    end)

    DispatchModel:reqEventList(true, true)

    self:refreshSeasonPassTime()
    self:schedule(1, function()
        self:refreshSeasonPassTime()
    end)
end

function P:onDestroy()
    DispatchModel:setLastCampInt(self._selectedCamp)
end

function P:evt_jumpDispatchEvent(params)
    local event = params.event
    local eventCfg = tpl_event_info[event.event_id]
    self._selectedCamp = eventCfg.campInt
    self._selectedEventId = event.event_id
    self._selectedEvent = nil
    local eventData = DispatchModel:getEvent(self._selectedEventId)
    for i,v in ipairs(eventData) do
        if v.id == event.id then
            self._selectedIndex = i
            break
        end
    end
    self:evt_dispatchEventList()
end

function P:refreshSeasonPassTime()
    local dt = tpl_constdata.Dispatch_End - bee.getServerTime()
    if dt <= 0 then
        self.Time:SetActive(false)
    else
        bee.setText(self.TextTime, TimeHelp:getTimeLeftStr(dt))
    end
end

function P:evt_dispatchEventList()
    if not self._isInit then
        self.LoadingMask:SetActive(false)
        self.AnimRoot:SetActive(true)
    end
    self:setTabList(true)
    self:setAffairCont()
    self:setAffairList()
    self:setDetailCont()
    self:evt_refreshTopInfo()

    if not self._isInit then
        self:showGuide()
        self._isInit = true
    end
end

function P:evt_refreshTopInfo()
    bee.invoke(self.GoldItem1, "setItemId", GPropId.CampDispatchUpgrade)
    bee.invoke(self.GoldItem1, "setCount", _N(ItemModel:getItemNumById(GPropId.CampDispatchUpgrade)))
    bee.invoke(self.GoldItem1, "setClickCallback", function()
        bee.logEvent("dispatch-campup-item")
    end)

    bee.invoke(self.GoldItem2, "setItemId", GPropId.AccelerateDispatch)
    bee.invoke(self.GoldItem2, "setCount", _N(ItemModel:getItemNumById(GPropId.AccelerateDispatch)))
    bee.invoke(self.GoldItem2, "setClickCallback", function()
        bee.logEvent("dispatch-timereduce-item")
    end)

    self:setTabList()
    self:setDetailCont()
end

function P:initTabList()
    self.tabList = UiListEx:create(self.TabListObj)
    self.tabList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.ItemTab)
    end)
    self.tabList:setRefreshFunc(function(data, item)
        self:setTabItem(item, data)
    end)
    self.tabList:setWidth(211)
end

function P:setTabList(isShowAnim)
    local datas = {}
    for k, v in pairs(tpl_camp_detail) do
        table.insert(datas, DispatchModel:getCampData(v.campInt))
    end
    table.sort(datas, function(a, b)
        local sumA = 100
        local sumB = 100
        if a.camp_level > b.camp_level then
            sumA = sumA + 10
        end
        if b.camp_level > a.camp_level then
            sumB = sumB + 10
        end
        if a.camp_id < b.camp_id then
            sumA = sumA + 1
        end
        if b.camp_id < a.camp_id then
            sumB = sumB + 1
        end
        return sumA > sumB
    end)
    self.tabList:setDatas(datas)

    if not self._isInit then
        for i, v in ipairs(datas) do
            if v.camp_id == self._selectedCamp then
                self.tabList:moveToYItem(i)
                break
            end
        end
    end
    
    if isShowAnim and self._tabItemUnlockAnim then
        for i, v in ipairs(datas) do
            if v.camp_id == self._tabItemUnlockAnim then
                self.tabList:moveToYItem(i)
                break
            end
        end
        for k, v in pairs(self.tabList:getShows()) do
            local node = self.tabList:getNode(v)
            local data = self.tabList:getData(v)
            if data.camp_id == self._tabItemUnlockAnim then
                self._tabItemUnlockAnim = nil
                local eff = AnimationMgr:playUIEffect("effect/Prefab/Dispatch/Eff_poker_Ui_Dispatch_js", self.node.transform)
                eff.transform.position = node.transform.position
                self.tabList._list.enabled = false
                self:once(1.5, function()
                    self.tabList._list.enabled = true
                end)
                break
            end
        end
    end
end

function P:setTabItem(item, data)
    local TabOn = self:find("TabOn", item)
    local CampLevel = self:find("CampLevel", item)
    local CampIcon = self:find("CampLevel/CampIcon", item)
    local Lock = self:find("Lock", item)
    local Level = self:find("Level", item)
    local LevelText = self:find("Level/LevelText", item)
    local UnlockTag = self:find("UnlockTag", item)
    local RewardTag = self:find("RewardTag", item)

    local campCfg = tpl_camp_detail[data.camp_id]
    bee.setIconInAtlas(CampIcon, campCfg.camp_icon)
    TabOn:SetActive(self._selectedCamp == data.camp_id)
    RewardTag:SetActive(DispatchModel:getCampEventIsCanReward(data.camp_id))

    if data.camp_level <= 0 then
        Level:SetActive(false)
        Lock:SetActive(true)

        bee.setIcon(CampLevel, "dispatch_main_tap_camp_bg_1", "Dispatch")
        UnlockTag:SetActive(ItemModel:getItemNumById(GPropId.CampDispatchUpgrade) >= tpl_camp_info[1].quality_up_cost2)
    else
        Level:SetActive(true)
        Lock:SetActive(false)
        UnlockTag:SetActive(false)

        bee.setText(LevelText, "Lv." .. data.camp_level)
        bee.setIcon(CampLevel, "dispatch_main_tap_camp_bg_" .. data.camp_level, "Dispatch")
    end

    local clickFunc = function()
        if self._selectedCamp == data.camp_id then
            return
        end
        bee.logEvent("dispatch-camp", data.camp_id)
        if data.camp_level <= 0 then
            Game:playSound("ui_button_confirm")
            DispatchModel:upgradeCamp(data.camp_id, function()
                self._playAffairItemAnim = true
                self._tabItemUnlockAnim = data.camp_id
                self._selectedCamp = data.camp_id
                self._selectedEventId = nil
            end)
            return
        end

        Game:playSound("ui_tab_switch_1")
        self._selectedCamp = data.camp_id
        self._selectedEventId = nil
        self._selectedIndex = 1
        self._playAffairItemAnim = true
        self:refreshTabSelected()
        self:setAffairCont()
        self:setAffairList()
        -- self:setDetailCont()
        self:playDetailAnim()
    end

    bee.removeAllClick(item)
    bee.addClick(item, function()
        clickFunc()
    end)

    bee.removeAllClick(CampLevel)
    bee.addClick(CampLevel, function()
        clickFunc()
    end)
end

function P:refreshTabSelected()
    for k, v in pairs(self.tabList:getShows()) do
        local TabOn = self:find("TabOn", self.tabList:getNode(v))
        TabOn:SetActive(self._selectedCamp == self.tabList:getData(v).camp_id)
    end
end

-- 事务列表
function P:setAffairCont()
    local campData = DispatchModel:getCampData(self._selectedCamp)
    local campLevel = campData.camp_level
    local campCfg = tpl_camp_detail[self._selectedCamp]

    bee.setText(self.AffairNameText, _F("LAB_DISPATCH_02", _T(campCfg.camp_name)))
    bee.setIcon(self.TopFrameBg1, "dispatch_main_directory_bg_0" .. campLevel .. "_1", "Dispatch")
    bee.setIcon(self.TopFrameBg2, "dispatch_main_directory_bg_0" .. campLevel .. "_2", "Dispatch")

    local campUpgradeCfg = tpl_camp_info[campLevel + 1]
    if not campUpgradeCfg then
        self.CampMax:SetActive(true)
        self.ImproveButton:SetActive(false)
        self.Quantity:SetActive(false)
    else
        self.CampMax:SetActive(false)
        self.ImproveButton:SetActive(true)
        self.Quantity:SetActive(true)

        local upgradeCfg = tpl_props[GPropId.CampDispatchUpgrade]
        bee.setIcon(self.QuantityIcon, upgradeCfg.icon)
        local costCount = self._selectedCamp == 0 and campUpgradeCfg.quality_up_cost1 or campUpgradeCfg.quality_up_cost2
        bee.setText(self.QuantityText, "x" .. _N(costCount))
    end

    -- 派遣刷新
    local remainFreeTimes = DispatchModel:getRemainFreeRefreshTimes()
    bee.setText(self.RefreshText, _F("LAB_DISPATCH_08", math.max(remainFreeTimes, 0)))

    if remainFreeTimes > 0 then
        self.PaidRefreshButton:SetActive(false)
        self.PaidGrayRefreshButton:SetActive(false)

        if DispatchModel:getCampIsCanRefresh(self._selectedCamp) then
            self.FreeRefreshButton:SetActive(true)
            self.FreeGrayRefreshButton:SetActive(false)
        else
            self.FreeRefreshButton:SetActive(false)
            self.FreeGrayRefreshButton:SetActive(true)
        end
    else
        self.FreeRefreshButton:SetActive(false)
        self.FreeGrayRefreshButton:SetActive(false)

        if DispatchModel:getCampIsCanRefresh(self._selectedCamp) then
            self.PaidRefreshButton:SetActive(true)
            self.PaidGrayRefreshButton:SetActive(false)
            bee.setIconInAtlas(self:find("Item/PaidRefreshIcon", self.PaidRefreshButton), tpl_props[GPropId.RefreshDispatch].icon)
            bee.setText(self:find("Item/PaidRefreshText", self.PaidRefreshButton), "x1")
        else
            self.PaidRefreshButton:SetActive(false)
            self.PaidGrayRefreshButton:SetActive(true)
            bee.setIconInAtlas(self:find("Item/PaidRefreshIcon", self.PaidGrayRefreshButton), tpl_props[GPropId.RefreshDispatch].icon)
            bee.setText(self:find("Item/PaidRefreshText", self.PaidGrayRefreshButton), "x1")
        end
    end
end

function P:initAffairList()
    self.affairList = UiListEx:create(self.AffairListObj)
    self.affairList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.ItemAffair)
    end)
    self.affairList:setRefreshFunc(function(data, item, isInit, index)
        self:setAffairItem(item, data, isInit, index)
    end)
    self.affairList:setTopBottom(20, 0)
    self.affairList:setWidth(140)
    self.affairList:addValueChanged(function()
        if next(self._affairListAnimTag) then
            for k, v in pairs(self._affairListAnimTag) do
                scheduler:removeTag(v)
            end
            self._affairListAnimTag = {}

            for i, v in ipairs(self.affairList:getShows()) do
                self.affairList:getNode(v):SetActive(true)
                AnimationMgr:playAnim(self:find("Ani_root", self.affairList:getNode(v)), "UI_1_DispatchStar_item_idle")
            end
        end
    end)
end

function P:setAffairList()
    local datas = {}
    for k, v in pairs(DispatchModel:getCampEventList(self._selectedCamp)) do
        local temp = {}
        for k1, v1 in pairs(v[1]) do
            temp[k1] = v1
        end
        for k1, v1 in pairs(tpl_event_info[v[1].event_id]) do
            temp[k1] = v1
        end
        table.insert(datas, temp)
    end
    table.sort(datas, function(a, b)
        local sumA = 10000
        local sumB = 10000

        if a.status == DispatchModel.EventStatus.Finish then
            sumA = sumA + 1000
        end
        if b.status == DispatchModel.EventStatus.Finish then
            sumB = sumB + 1000
        end

        if a.status == DispatchModel.EventStatus.Dispatching then
            sumA = sumA + 100
        end
        if b.status == DispatchModel.EventStatus.Dispatching then
            sumB = sumB + 100
        end

        if a.event_level > b.event_level then
            sumA = sumA + 10
        end
        if b.event_level > a.event_level then
            sumB = sumB + 10
        end

        if a.id < b.id then
            sumA = sumA + 1
        end
        if b.id > a.id then
            sumB = sumB + 1
        end

        return sumA > sumB
    end)
    if not self._selectedEventId then
        self._selectedEventId = datas[1].event_id
    end
    self.affairList:setDatas(datas)
    self:playAffairItemAnim()
end

function P:playAffairItemAnim()   
    for k, v in pairs(self._affairListAnimTag) do
        scheduler:removeTag(v)
    end
    self._affairListAnimTag = {}

    if not self._playAffairItemAnim then
        return
    end
    self._playAffairItemAnim = false

    local addTime = self._isFirstAnim and 0.3 or 0
    for i, v in ipairs(self.affairList:getShows()) do
        self.affairList:getNode(v):SetActive(false)
        self._affairListAnimTag[self.affairList:getNode(v)] = self:once(0.1 * (i - 1) + addTime, function()
            if self.affairList:getNode(v) then
                self.affairList:getNode(v):SetActive(true)
                AnimationMgr:playAnim(self:find("Ani_root", self.affairList:getNode(v)), "UI_1_DispatchStar_item")
            end
        end)
    end
    self._isFirstAnim = false
end

function P:setAffairItem(item, data, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    local AffairFrame = self:find("AffairFrame", Ani_root)
    local LevelIcon = self:find("LevelIcon", Ani_root)
    local AffairNameText = self:find("Text/AffairNameText", Ani_root)
    local AffairTimeText = self:find("Text/AffairTimeText", Ani_root)
    local TimeIcon = self:find("Text/TimeIcon", Ani_root)
    local TimeAnimIcon = self:find("Text/TimeAnimIcon", Ani_root)
    local Avatar = self:find("Condition/Avatar", Ani_root)
    local AvatarIcon = self:find("Condition/Avatar/gacha_outfit_avatar_02/AvatarIcon", Ani_root)
    local AwardButton = self:find("Condition/AwardButton", Ani_root)
    local AddonButton = self:find("Condition/AddonButton", Ani_root)
    local RewardTag = self:find("RewardTag", Ani_root)
    local Selected = self:find("Selected", Ani_root)
    RewardTag:SetActive(false)

    bee.setIcon(AffairFrame, "dispatch_main_directory_task_bg_0" .. data.event_level, "Dispatch")
    bee.setIcon(LevelIcon, "dispatch_main_directory_task_level_0" .. data.event_level, "Dispatch")
    bee.setText(AffairNameText, _T(data.event_name))

    Selected:SetActive(data.event_id == self._selectedEventId)

    if self._affairTimeTag[item] then
        scheduler:removeTag(self._affairTimeTag[item])
        self._affairTimeTag[item] = nil
    end

    TimeIcon:SetActive(true)
    TimeAnimIcon:SetActive(false)

    local events = DispatchModel:getEvent(data.event_id)
    local eventData = events[1]
    if eventData.status == DispatchModel.EventStatus.NoDispatch then
        Avatar:SetActive(false)
        AddonButton:SetActive(true)
        AwardButton:SetActive(false)

        local campData = DispatchModel:getCampData(self._selectedCamp)
        local campCfg = tpl_camp_info[campData.camp_level]
        bee.setText(AffairTimeText, DispatchModel:getDispatchTimeText1(data.base_time * (1 - campCfg.time_reduce / 10000)))
    else
        if eventData.end_ts > bee.getServerTime() then
            Avatar:SetActive(true)
            AddonButton:SetActive(false)
            AwardButton:SetActive(false)

            local role = CharacterModel:getRole(eventData.role_id)
            local skinCfg = role:getSkinData()
            bee.setIconInAtlas(AvatarIcon, tpl_props[skinCfg.avatar].icon)

            local time = eventData.end_ts - bee.getServerTime()
            if time > 0 then
                TimeIcon:SetActive(false)
                TimeAnimIcon:SetActive(true)

                bee.setText(AffairTimeText, DispatchModel:getDispatchTimeText2(time))
                self._affairTimeTag[item] = self:schedule(1, function()
                    local time = eventData.end_ts - bee.getServerTime()
                    if time > 0 then
                        bee.setText(AffairTimeText, DispatchModel:getDispatchTimeText2(time))
                    else
                        self:setAffairItem(item, data)
                    end
                end)
            else
                self:setAffairItem(item, data)
            end
        elseif eventData.status == DispatchModel.EventStatus.Finish or eventData.end_ts <= bee.getServerTime() then
            Avatar:SetActive(false)
            AddonButton:SetActive(false)
            AwardButton:SetActive(true)
            RewardTag:SetActive(true)
            bee.setText(AffairTimeText, _T("LAB_DISPATCH_17"))
        end
    end

    bee.removeAllClick(item)
    bee.addClick(item, function()
        if self._selectedEventId == data.event_id then
            return
        end
        Game:playSound("ui_tab_switch_1")
        bee.logEvent("dispatch-view", self._selectedCamp, data.event_id)
        self._selectedEventId = data.event_id
        self._selectedIndex = 1
        -- self:setDetailCont()
        self:playDetailAnim()
        self:refreshArrairItemSelected()
    end)

    -- 领取奖励
    bee.removeAllClick(AwardButton)
    bee.addClick(AwardButton, function()
        if not eventData then
            return
        end

        self:_claimReward(eventData, function()
            if self._selectedEventId == data.event_id then
                self._selectedEventId = nil
                self._selectedEvent = nil
                self._selectedIndex = nil
            end
        end)
    end)
end

function P:refreshArrairItemSelected()
    for k, v in pairs(self.affairList:getShows()) do
        self:find("Ani_root/Selected", self.affairList:getNode(v)):SetActive(self.affairList:getData(v).event_id == self._selectedEventId)
    end
end

function P:setDetailCont()
    local eventInfo = tpl_event_info[self._selectedEventId]
    if not eventInfo then
        return
    end

    if self._emojiAnimTag then
        scheduler:removeTag(self._emojiAnimTag)
        self._emojiAnimTag = nil
    end
    self.EmojiAnim:SetActive(false)
    
    bee.setIcon(self.DetailFrame, "dispatch_main_details_title_bg_0" .. eventInfo.event_level, "Dispatch")
    bee.setText(self.DetailNameText, _T(eventInfo.event_name))

    local eventData = DispatchModel:getEvent(self._selectedEventId)
    if eventData and eventData[1] and eventData[1].status ~= DispatchModel.EventStatus.NoDispatch then
        self:setDispatchingDetail()
    else
        self:setNormalDetail()
    end
end

function P:playDetailAnim()
    AnimationMgr:playAnim(self.Detail, "UI_2_Detail_back", function()
        self:setDetailCont()
        AnimationMgr:playAnim(self.Detail, "UI_2_Detail_into")
    end)
end

function P:setNormalDetail()
    self.Normal:SetActive(true)
    self.Dispatching:SetActive(false)

    local campData = DispatchModel:getCampData(self._selectedCamp)
    if not campData then
        return
    end
    local campLevel = campData.camp_level
    local campCfg = tpl_camp_info[campLevel]

    local eventInfo = tpl_event_info[self._selectedEventId]
    local eventData = DispatchModel:getEvent(self._selectedEventId)
    if not eventData or not eventInfo then
        return
    end

    local event = eventData[1]
    self._selectedEvent = event

    -- 奖励道具
    local add = campCfg.base_reward_up
    -- 玩家等级经验
    if eventInfo.reward_exp > 0 and DispatchModel:isCanRewardExp() then
        self.ExpAwardItem:SetActive(true)
        local num = math.ceil(eventInfo.reward_exp * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.ExpAwardItem), {item_id = GPropId.ExpDispatch, num = num}):bindTips()
        if add > 0 then
            self:find("Buff", self.ExpAwardItem):SetActive(true)
            bee.setText(self:find("Buff/NumText", self.ExpAwardItem), add / 100 .. "%")
        else
            self:find("Buff", self.ExpAwardItem):SetActive(false)
        end
    else
        self.ExpAwardItem:SetActive(false)
    end
    -- 派遣角色好感度
    if eventInfo.reward_affinity > 0 and DispatchModel:isCanRewardBond() then
        self.BondAwardItem:SetActive(true)
        local num = math.ceil(eventInfo.reward_affinity * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.BondAwardItem), {item_id = GPropId.BondDispatch, num = num}):bindTips()
        if add > 0 then
            self:find("Buff", self.BondAwardItem):SetActive(true)
            bee.setText(self:find("Buff/NumText", self.BondAwardItem), add / 100 .. "%")
        else
            self:find("Buff", self.BondAwardItem):SetActive(false)
        end
    else
        self.BondAwardItem:SetActive(false)
    end
    -- 角色星级经验
    if eventInfo.reward_star_exp > 0 then
        self.RoleStarAwardItem:SetActive(true)
        local num = math.ceil(eventInfo.reward_star_exp * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.RoleStarAwardItem), {item_id = GPropId.RoleDispatchExp, num = num}):bindTips()
        if add > 0 then
            self:find("Buff", self.RoleStarAwardItem):SetActive(true)
            bee.setText(self:find("Buff/NumText", self.RoleStarAwardItem), add / 100 .. "%")
        else
            self:find("Buff", self.RoleStarAwardItem):SetActive(false)
        end
    else
        self.RoleStarAwardItem:SetActive(false)
    end
    -- 事务所品质提升/解锁道具
    if eventInfo.reward_campquality > 0 then
        self.DispatchExpAwardItem:SetActive(true)
        local num = math.ceil(eventInfo.reward_campquality * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.DispatchExpAwardItem), {item_id = GPropId.CampDispatchUpgrade, num = num}):bindTips()
        if add > 0 then
            self:find("Buff", self.DispatchExpAwardItem):SetActive(true)
            bee.setText(self:find("Buff/NumText", self.DispatchExpAwardItem), add / 100 .. "%")
        else
            self:find("Buff", self.DispatchExpAwardItem):SetActive(false)
        end
    else
        self.DispatchExpAwardItem:SetActive(false)
    end
    -- 彩蛋奖励
    self.RewardBonusAwardItem:SetActive(false)

    -- 派遣时间
    bee.setText(self.DetailTimeText, DispatchModel:getDispatchTimeText1(eventInfo.base_time * (1 - campCfg.time_reduce / 10000)))

    -- 星级限制
    if eventInfo.character_level == 0 then
        self.StarText:SetActive(true)
        self.Stars:SetActive(false)
        bee.setText(self.StarText, _T("LAB_DISPATCH_18"))
    else
        self.StarText:SetActive(false)
        self.Stars:SetActive(true)
        for i = 1, 5 do
            self:find("Star" .. i, self.Stars):SetActive(i <= eventInfo.character_level)
        end
    end

    -- 单次派遣人数上限
    bee.setText(self.RoleText, campCfg.members_limit)

    -- 普通派遣
    local ordinaryTimes = DispatchModel:getRemainOrdinaryTimes()
    bee.setText(self.OrdinaryNumText, _F("LAB_DISPATCH_23", ordinaryTimes, tpl_constdata.Dispatch_Ordinary_Num))
    bee.setIconInAtlas(self.OrdinaryIcon, tpl_props[GPropId.OrdinaryDispatch].icon)
    local curOrdinaryCount = ItemModel:getItemNumById(GPropId.OrdinaryDispatch)
    if not GuideManager:checkGuidePlayed(23002) then
        curOrdinaryCount = math.max(curOrdinaryCount - tpl_constdata.Dispatch_Free_Num, 0)
    end
    bee.setText(self.OrdinaryText, _T("LAB_BACKPACK_DES_22") .. "<color=#C6C6C6>" .._N2(curOrdinaryCount) .. "</color>")

    -- 高级派遣
    bee.setIconInAtlas(self.SeniorIcon, tpl_props[GPropId.SeniorDispatch].icon)
    local curSeniorCount = ItemModel:getItemNumById(GPropId.SeniorDispatch)
    bee.setText(self.SeniorText, _T("LAB_BACKPACK_DES_22") .. "<color=#C6C6C6>" .._N2(curSeniorCount) .. "</color>")
end

function P:setDispatchingDetail()
    self.Normal:SetActive(false)
    self.Dispatching:SetActive(true)

    local eventInfo = tpl_event_info[self._selectedEventId]
    local eventData = DispatchModel:getEvent(self._selectedEventId)
    if not eventData or not eventInfo then
        return
    end
    if self._selectedEvent then
        for i,v in ipairs(eventData) do
            if self._selectedEvent.id == v.id then
                self._selectedIndex = i
                break
            end
        end
    end
    if not self._selectedIndex then
        self._selectedIndex = 1
    end
    local eventCount = #eventData
    local event = eventData[self._selectedIndex]
    local eventCfg = tpl_event_info[event.event_id]
    self._selectedEvent = event
    
    bee.setText(self.RoleCountText, "x" .. eventCount)
    self.Arrow:SetActive(eventCount > 1)
    self._maxRoleCount = eventCount

    -- 时间状态
    if self._dispatchingTimeTag then
        scheduler:removeTag(self._dispatchingTimeTag)
        self._dispatchingTimeTag = nil
    end
    local time = event.end_ts - bee.getServerTime()
    if time > 0 then
        self.AccelerateButton:SetActive(true)
        self.Claim:SetActive(false)
        self.DispatchingTimeText:SetActive(true)
        self.CompletedText:SetActive(false)
        bee.setText(self.StatusText, _T("LAB_DISPATCH_16"))
        bee.setText(self.DispatchingTimeText, DispatchModel:getDispatchTimeText2(time))
        self._dispatchingTimeTag = self:schedule(1, function()
            time = event.end_ts - bee.getServerTime()
            if time > 0 then
                bee.setText(self.DispatchingTimeText, DispatchModel:getDispatchTimeText2(time))
            else
                scheduler:removeTag(self._dispatchingTimeTag)
                self._dispatchingTimeTag = nil
                self.AccelerateButton:SetActive(false)
                self.Claim:SetActive(true)
                bee.setText(self.DispatchingTimeText, "")
                self.DispatchingTimeText:SetActive(false)
                self.CompletedText:SetActive(true)
                bee.setText(self.StatusText, "<color=#E8D85C>" .. _T("LAB_DISPATCH_17") .. "</color>")
            end
        end)
    else
        self.AccelerateButton:SetActive(false)
        self.Claim:SetActive(true)
        bee.setText(self.DispatchingTimeText, "")
        self.DispatchingTimeText:SetActive(false)
        self.CompletedText:SetActive(true)
        bee.setText(self.StatusText, "<color=#E8D85C>" .. _T("LAB_DISPATCH_17") .. "</color>")
    end

    -- 角色buff
    local role = CharacterModel:getRole(event.role_id)
    local roleInfo = tpl_character_info[event.role_star]
    if role.info.campInt == eventCfg.campInt and roleInfo.reward_bonus > 0 then
        self.RewardBonusBuff:SetActive(true)
        bee.setText(self:find("BuffText", self.RewardBonusBuff), roleInfo.reward_bonus / 100 .. "%")
    else
        self.RewardBonusBuff:SetActive(false)
    end
    if roleInfo.base_reward_up > 0 then
        self.BaseRewardUpBuff:SetActive(true)
        bee.setText(self:find("BuffText", self.BaseRewardUpBuff), roleInfo.base_reward_up / 100 .. "%")
    else
        self.BaseRewardUpBuff:SetActive(false)
    end
    if roleInfo.time_reduce > 0 then
        self.TimeReduceBuff:SetActive(true)
        bee.setText(self:find("BuffText", self.TimeReduceBuff), roleInfo.time_reduce / 100 .. "%")
    else
        self.TimeReduceBuff:SetActive(false)
    end
    if role.info.campInt ~= eventCfg.campInt then
        self.DecelerateBuff:SetActive(true)
        bee.setText(self:find("BuffText", self.DecelerateBuff), "-" .. tpl_constdata.Dispatch_Camp_Debuff / 100 .. "%")
    else
        self.DecelerateBuff:SetActive(false)
    end
    bee.setIcon(self.RoleCampIcon, "dispatch_main_details_bg_camp_" .. role.info.campInt, "Dispatch", true)

    -- 角色立绘
    if not self._characterCls then
        self._characterCls = ObjectPool:getCls(self.CharacterImageRaw)
        self._characterCls:createRoleCanvas()
    end
    self._characterCls:setRole(role)

    local skinCfg = role:getSkinData()
    skinCfg = GF.getShowSkinData(skinCfg, self._showReal)
    self._characterCls:setSkin(role:getSkinData())
    local posInfo = skinCfg.dispatch_offset
    self._characterCls:setRoleOffset(bee.v3(posInfo[1], posInfo[2], 1), bee.v3(posInfo[3], posInfo[3], 1))

    self:setEmojiAnim(role)

    -- 奖励显示
    if event.exp > 0 then
        self.ExpRewardItem:SetActive(true)
        PropItem:create(self:find("PropItem", self.ExpRewardItem), {item_id = GPropId.ExpDispatch, num = event.exp}):bindTips()
        if event.base_reward_up > 0 then
            self:find("BaseRewardUp", self.ExpRewardItem):SetActive(true)
            bee.setText(self:find("Text", self:find("BaseRewardUp", self.ExpRewardItem)), event.base_reward_up / 100 .. "%")
        else
            self:find("BaseRewardUp", self.ExpRewardItem):SetActive(false)
        end
    else
        self.ExpRewardItem:SetActive(false)
    end
    if event.bond > 0 then
        self.BondRewardItem:SetActive(true)
        PropItem:create(self:find("PropItem", self.BondRewardItem), {item_id = GPropId.BondDispatch, num = event.bond}):bindTips()
        if event.base_reward_up > 0 then
            self:find("BaseRewardUp", self.BondRewardItem):SetActive(true)
            bee.setText(self:find("Text", self:find("BaseRewardUp", self.BondRewardItem)), event.base_reward_up / 100 .. "%")
        else
            self:find("BaseRewardUp", self.BondRewardItem):SetActive(false)
        end
    else
        self.BondRewardItem:SetActive(false)
    end
    if event.star_exp > 0 then
        self.RoleStarRewardItem:SetActive(true)
        PropItem:create(self:find("PropItem", self.RoleStarRewardItem), {item_id = GPropId.RoleDispatchExp, num = event.star_exp}):bindTips()
        if event.base_reward_up > 0 then
            self:find("BaseRewardUp", self.RoleStarRewardItem):SetActive(true)
            bee.setText(self:find("Text", self:find("BaseRewardUp", self.RoleStarRewardItem)), event.base_reward_up / 100 .. "%")
        else
            self:find("BaseRewardUp", self.RoleStarRewardItem):SetActive(false)
        end
    else
        self.RoleStarRewardItem:SetActive(false)
    end
    if event.camp_quality > 0 then
        self.DispatchExpRewardItem:SetActive(true)
        PropItem:create(self:find("PropItem", self.DispatchExpRewardItem), {item_id = GPropId.CampDispatchUpgrade, num = event.camp_quality}):bindTips()
        if event.base_reward_up > 0 then
            self:find("BaseRewardUp", self.DispatchExpRewardItem):SetActive(true)
            bee.setText(self:find("Text", self:find("BaseRewardUp", self.DispatchExpRewardItem)), event.base_reward_up / 100 .. "%")
        else
            self:find("BaseRewardUp", self.DispatchExpRewardItem):SetActive(false)
        end
    else
        self.DispatchExpRewardItem:SetActive(false)
    end

    -- 彩蛋奖励
    if self.bonusRewardItems then
        for k,v in pairs(self.bonusRewardItems) do
            CU.GameObject.Destroy(v)
        end
        self.bonusRewardItems = nil
    end
    -- 彩蛋奖励
    -- if event.end_ts <= bee.getServerTime() then
    --     self.RewardBonusRewardItem:SetActive(false)
    --     -- 已完成时显示最终奖励
    --     if event.reward_bonus then
    --         self.bonusRewardItems = {}
    --         for i = 1, #event.reward_bonus, 2 do
    --             local copyItem = CU.GameObject.Instantiate(self.RewardItem)
    --             copyItem.transform:SetParent(self.RewardListCont.transform)
    --             copyItem.transform.localScale = bee.v3(1, 1, 1)
    --             copyItem.transform.localPosition = bee.v3(0, 0, 0)
    --             copyItem.transform:SetAsFirstSibling()
    --             copyItem:SetActive(true)
    --             table.insert(self.bonusRewardItems, copyItem)

    --             PropItem:create(self:find("PropItem", copyItem), {item_id = event.reward_bonus[i], num = event.reward_bonus[i + 1]}):bindTips()
    --         end
    --     end
    -- else
        if eventInfo.reward_bonus_item then
            local isBonus = role.info.campInt == eventInfo.campInt
            if isBonus then
                self.RewardBonusRewardItem:SetActive(true)
                PropItem:create(self:find("PropItem", self.RewardBonusRewardItem), {item_id = GPropId.DispatchBonus, num = 0})

                local bonusAdd = eventInfo.reward_bonus or 0
                if roleInfo then
                    bonusAdd = bonusAdd + roleInfo.reward_bonus
                end
                if bonusAdd > 0 then
                    self:find("Buff", self.RewardBonusRewardItem):SetActive(true)
                    bee.setText(self:find("Buff/NumText", self.RewardBonusRewardItem), bonusAdd / 100 .. "%")
                else
                    self:find("Buff", self.RewardBonusRewardItem):SetActive(false)
                end

                bee.removeAllClick(self:find("PropItem", self.RewardBonusRewardItem))
                bee.addClick(self:find("PropItem", self.RewardBonusRewardItem), function()
                    local rewardsBonus = {}
                    for i = 1, #eventInfo.reward_bonus_item, 3 do
                        table.insert(rewardsBonus, {item_id = eventInfo.reward_bonus_item[i], num = eventInfo.reward_bonus_item[i + 1], weight = eventInfo.reward_bonus_item[i + 2]})
                    end
                    UiManager:showUI("DispatchRewardBondTip", {items = rewardsBonus, target = self.RewardBonusRewardItem})
                end)
            else
                self.RewardBonusRewardItem:SetActive(false)
            end
        else
            self.RewardBonusRewardItem:SetActive(false)
        end
    -- end
end

function P:onClickClaimReward()
    self:_claimReward(self._selectedEvent, function()
        self._selectedEventId = nil
        self._selectedEvent = nil
        self._selectedIndex = nil
    end)
end

function P:_claimReward(event, cb)
    if not bee.checkCd("DispatchClaimReward", 1) then
        return
    end
    bee.logEvent("dispatch-claim-rewards", self._selectedCamp, self._selectedEventId)
    if cb then
        cb()
    end
    DispatchModel:reqRecReward(event, function()
        if DispatchModel:getSkipPlot() then
            self:once(0.5, function()
                DispatchModel:showRecReward()
            end)
        else
            DispatchModel:playStory(event, function()
                DispatchModel:showRecReward()
            end)
        end
    end)
end

function P:setEmojiAnim(role)
    local emojis = get_tpl_subKey(tpl_emoji_list, "role", role.role_id)
    local emojiList = {}
    for k,v in pairs(emojis) do
        if not v.unlock or v.unlock <= role:getBondLevel() then
            table.insert(emojiList, v)
        end
    end

    if self._emojiAnimTag then
        scheduler:removeTag(self._emojiAnimTag)
        self._emojiAnimTag = nil
    end

    self.EmojiAnim:SetActive(false)
    self._emojiAnimTag = self:schedule(20, function()
        local rand = math.random(#emojiList)
        bee.setIcon(self:find("Chat_Ani/ImageEmoji/ImageEmoji", self.EmojiAnim), emojiList[rand].emoji)
        self.EmojiAnim:SetActive(false)
        self.EmojiAnim:SetActive(true)
    end)
end

function P:showGuide()
    if not GuideManager:checkGuidePlayed(23002) then
        UiManager:showUI("Story", {id = 100100, hideScene = true, fastSkip = true, hideCb = function()
            GuideManager:startSystemGuide(23002, 0.65)
        end})
    end
end

function P:evt_guide_end(data)
    if data.id == 23012 then
        UiManager:showUI("BackpackClaimResult", {items = {{id = GPropId.OrdinaryDispatch, num = tpl_constdata.Dispatch_Free_Num}}})
        self:setDetailCont()
    end
end

return P