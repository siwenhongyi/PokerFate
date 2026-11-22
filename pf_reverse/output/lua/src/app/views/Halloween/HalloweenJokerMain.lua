local P = class("HalloweenJokerMain", require("app.views.Halloween.HalloweenBase"))

function P:onAwake()
    BalBattleModel:initRequire()
    P.super.onAwake(self)
    self.inBalatroGame = true

    --当前的鬼牌节点
    self.JokerSlotRoot = self:find("JokerCardList", self.Center)
    self.JokerSlotsScroll = self.JokerSlotRoot:GetComponent("ScrollRect")
    self.JokerSlotList = self:initJokerSlot()
    self.JokerList = {}
    --进度奖励
    self.RewardScrollView = self:find("RewardList", self.Center)
    self.RewardItem = self:find("RewardItem", self.RewardScrollView)
    self.RewardItem:SetActive(false)
    self.RewardList = UiListEx:create(self.RewardScrollView)
    self.RewardList:setWidth(164)
    self.RewardList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.RewardItem)
    end)
    self.RewardList:setRefreshFunc(function(data, item, isInit, index)
        self:refreshRewardItem(data, item, isInit, index)
    end)
    self.progressLine = self:find("Viewport/Content/halloween_joker_main_slider_bg_01", self.RewardScrollView)
    self.curRewardIndex = nil

    --鬼牌详情
    self.JokerInfoMask = self:find("InfoMask", self.Center)
    bee.addClick(self.JokerInfoMask, function()
        self:closeJokerInfo()
    end)

    --奖励上限
    self.Obtained = self:find("Obtained", self.Center)
    self.ObtainedValue = self:find("Value", self.Obtained)

    self._scale = 1

    --退出
    -- bee.addClick(self:find("Return"), function ()
    --     Game:playSound("ui_button_confirm")
    --     self:hideUI()
    -- end)

    --牌型
    bee.addClick(self:find("OrderButton", self.Left), function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HalloweenCard")
        bee.logEvent("joker-info", 1)
    end)

    --开始
    bee.addClick(self:find("Bottom/EnterButton", self.AnimRoot), function ()
        if not bee.checkCd("BalatroGameStart", 2) then
            return
        end
        Game:playSound("ui_button_confirm")
        BalBattleModel:startChallenge()
        bee.logEvent("joker-start", BalBattleModel.curLevel)
        -- UiManager:showUI("BalatroGame")
    end)
end

function P:onStart()
    BalBattleModel:getClownInfo()

    local lang = LanguageManager:getLanguage()
    local TitleRoot = self:find("Top/Title", self.AnimRoot)
    local EnterRoot = self:find("Bottom/EnterButton", self.AnimRoot)
    for _, v in ipairs(Config.Languages) do
        local title = self:find("halloween_joker_main_title_" .. v, TitleRoot)
        local enterText = self:find("halloween_joker_main_enter_" .. v, EnterRoot)
        if title then
            title:SetActive(v == lang)
        end
        if enterText then
            enterText:SetActive(v == lang)
        end
    end
    -- for i = 1, 4 do
    --     self:find
    -- end


    -- local jokerSkills = {1, 2, 3, 4}
    -- for k,v in pairs(jokerSkills) do
    --     local jokerData = JokerUtil:creatNewJokerData()
    --     jokerData.uid = k
    --     jokerData.skillId = v
    --     table.insert(BBM.ownedJokerList, jokerData)

    --     BSM:initJokerEffect(jokerData)
    -- end
    -- self:createJokers()
    -- BBM:setCardTypeLv()
end

function P:evt_refreshBalatroData()
    self:halloweenJokerGuide()
    self:createJokers()
    local datas = {}
    for _,v in pairs(tpl_fate_main_level) do
        table.insert(datas, {id = v.id, index = v.num, rewards = v.rewards, endless = v.is_infinite ~= nil})
    end
    table.sort(datas, function(a, b) return a.id < b.id end)
    self.curRewardIndex = nil
    for i, v in ipairs(datas) do
        if v.id == BalBattleModel.curLevel then
            self.curRewardIndex = i
            break
        end
    end
    self.RewardList:setTopBottom(0, 0)
    self.RewardList:setDatas(datas, true, false)
    self.progressLine.transform.sizeDelta = bee.v2(164 * (#datas - 1), self.progressLine.transform.sizeDelta.y)
    self:jumpToCurReward()

    local lvCfg = tpl_fate_main_level[BalBattleModel.curLevel]
    if lvCfg.is_infinite then
        self.Obtained:SetActive(true)
        local curCount = BalBattleModel.endlessTime * lvCfg.rewards[2]
        local limitCount = lvCfg.count * lvCfg.rewards[2]
        bee.setText(self.ObtainedValue, string.format("%d/%d", curCount, limitCount))
    else
        self.Obtained:SetActive(false)
    end
end

--初始化鬼牌槽位
function P:initJokerSlot()
    local list = {}
    local content = self.JokerSlotsScroll.content
    for i = 1, BalBattleModel.maxJokerSlot do
        local slot = {}
        slot.index = i
        slot.tran = self:find("Slot" .. i, content).transform
        slot.ani = self:find("Ani_root", slot.tran)
        slot.center = self:find("center", slot.ani)
        slot.lock = self:find("card_joker_mask", slot.ani)
        slot.tip = self:find("Tip", slot.ani)
        bee.addClick(slot.lock, function ()
            self:unlockTip(slot.index)
        end)
        table.insert(list, slot)
    end
    return list
end

--实例化鬼牌
function P:createJokers()
    local slotCount = table.nums(self.JokerSlotList)
    for i = 1, slotCount do
        local slotIndex = i
        self:once(0.1 * (i - 1), function ()
            self.JokerSlotList[slotIndex].tran.gameObject:SetActive(true)
        end)
        self.JokerSlotList[slotIndex].tran.gameObject:SetActive(false)
    end

    local index = 0
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        index = index + 1
        local jokerItem = self.JokerList[index]
        if jokerItem == nil then
            self:createJoker(index, v)
        else
            if jokerItem.data.skillId ~= v.skillId or jokerItem.data.uid == 0 then
                BaseCardUtil:recoveryCard(jokerItem)
                self:createJoker(index, v)
            end
        end
    end
    for i = index + 1, BalBattleModel.maxJokerSlot do
        self:createUnlockJoker(i)
    end
end
function P:createJoker(index, jokerData)
    local joker = bee.createObj("views/Halloween/HalloweenCardJoker")
    joker.transform:SetParent(self.JokerSlotList[index].center.transform, false)
    joker.transform.localPosition = bee.v3zero
    local jokerCls = ObjectPool:getCls(joker)
    jokerCls:setData(jokerData)
    jokerCls.index = index
    self.JokerList[index] = jokerCls
    jokerCls.btn.onClick:AddListener(function () self:showJokerDetail(jokerCls) end)
    jokerCls.btn.onBeginDrag:AddListener(function (go, eventData) self:onBeginDrag(jokerCls, eventData) end)
    jokerCls.btn.onDrag:AddListener(function (go, eventData) self:onDrag(jokerCls, eventData) end)
    jokerCls.btn.onEndDrag:AddListener(function (go, eventData) self:onEndDrag(jokerCls, eventData) end)
    -- jokerCls.btn.onPress:AddListener(function () self:onLongPress(jokerCls) end)
    jokerCls.btn.onDown:AddListener(function () self:onDown(jokerCls) end)
    jokerCls.btn.onUp:AddListener(function () self:onUp(jokerCls) end)

    jokerCls:setRefresh(true)
    self.JokerSlotList[index].lock:SetActive(false)
    self.JokerSlotList[index].tip:SetActive(false)
end
function P:createUnlockJoker(index)
    local card = bee.createObj("views/Halloween/HalloweenCardJoker")
    card.transform:SetParent(self.JokerSlotList[index].center.transform, false)
    card.transform.localPosition = bee.v3zero
    local jokerCls = ObjectPool:getCls(card)
    jokerCls:setUnlockData()
    jokerCls.index = index
    self.JokerList[index] = jokerCls

    jokerCls:setRefresh(false)
    self.JokerSlotList[index].lock:SetActive(true)
    self.JokerSlotList[index].tip:SetActive(true)
    local openDay = ThemeModel:getOpenDay() + 1
    local seatCfg = tpl_fate_seat[index]
    local unlockDay = seatCfg.day or 0
    bee.setText(self.JokerSlotList[index].tip, _F("TAB_JOKER_DEC_29", unlockDay - openDay))
end

function P:evt_refreshJokerData(slotId)
    local jokerData = BalBattleModel.ownedJokerList[slotId]
    local jokerCls = self.JokerList[slotId]
    jokerCls:refreshJokerCallback(jokerData)
    Game:playSound("ui_7daytask_progress_add_2")
    bee.logEvent("joker-refresh", slotId)

    self:closeJokerInfo()
end

--显示详情
function P:showJokerDetail(jokerCls)
    if jokerCls.draging or jokerCls.tweening then
        return
    end

    if jokerCls.selecting then
        self:closeJokerInfo(jokerCls)
        return
    end

    for _,v in pairs(self.JokerList) do
        if v.selecting then
            BaseCardUtil:SwitchCardSelecting(v)
            break
        end
    end

    BaseCardUtil:SwitchCardSelecting(jokerCls, true)
    JokerUtil:showJokerDetail(jokerCls, self.JokerInfoMask)
end

-- function P:onLongPress(jokerCls)
--     if jokerCls.draging then
--         return
--     end
--     if not jokerCls.longPress then
--         jokerCls.longPress = true
--         jokerCls.transform:SetParent(self.JokerSlotsScroll.content, true)
--         BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.changan)
--     end
-- end
function P:onBeginDrag(jokerCls, eventData)
    jokerCls.draging = true
    -- self.JokerSlotsScroll:OnBeginDrag(eventData)
    jokerCls.transform:SetParent(self.JokerSlotsScroll.content, true)
    BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.changan, true)
    if self.JokerInfoMask.activeSelf then
        self:closeJokerInfo()
    end
end
function P:onDrag(jokerCls, eventData)
    jokerCls.transform.localPosition = jokerCls.transform.localPosition + bee.v3(eventData.delta.x / self._scale, eventData.delta.y / self._scale, 0)
    -- self:checkScrollMove(jokerCls)
    self:checkMove(jokerCls)

    -- self.JokerSlotsScroll:OnDrag(eventData)
end
function P:onEndDrag(jokerCls, eventData)
    jokerCls.draging = false
    BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.daiji, true)
    self:moveToSolt(jokerCls.index)

    -- self.JokerSlotsScroll:OnEndDrag(eventData)
end
function P:onDown(jokerCls)
    -- jokerCls.longPress = false
    local canvas = UiManager:getPopRoot():GetComponent("Canvas")
    if not bee.isNull(canvas) and canvas.scaleFactor and canvas.scaleFactor ~= 0 then
        self._scale = canvas.scaleFactor
    end
end
function P:onUp(jokerCls)
    -- if jokerCls.longPress then
    --     jokerCls.longPress = false
    --     BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.daiji)
    -- end
end

--检测Scroll滑动
function P:checkScrollMove(jokerCls)
    local scrollSize = self.JokerSlotsScroll.transform.sizeDelta
    local content = self.JokerSlotsScroll.content
    local contentSize = content.sizeDelta
    local contentPos = content.localPosition
    local jokerPos = jokerCls.transform.localPosition
    local halfCardWidth = jokerCls.transform.sizeDelta.x * 0.5
    local maxScroll = math.max(contentSize.x - scrollSize.x, 0)
    local targetContentX = contentPos.x

    if jokerPos.x + halfCardWidth > scrollSize.x - contentPos.x then
        targetContentX = scrollSize.x - jokerPos.x - halfCardWidth
    elseif jokerPos.x - halfCardWidth < -contentPos.x then
        targetContentX = halfCardWidth - jokerPos.x
    else
        return
    end

    targetContentX = math.max(-maxScroll, math.min(targetContentX, 0))
    if targetContentX == contentPos.x then
        return
    end

    content.localPosition = bee.v3(targetContentX, contentPos.y, contentPos.z)
    jokerCls.transform.localPosition = bee.v3(
        jokerPos.x + contentPos.x - targetContentX,
        jokerPos.y,
        jokerPos.z
    )
end

--检测滑动
function P:checkMove(jokerCls)
    if not jokerCls or not jokerCls.transform or not jokerCls.index then
        return
    end

    local jokerTran = jokerCls.transform
    local jokerIndex = jokerCls.index

    while jokerIndex > 1 do
        local leftJoker = self.JokerList[jokerIndex - 1]
        if not leftJoker or jokerTran.position.x >= leftJoker.transform.position.x or leftJoker.data.uid == 0 then
            break
        end

        local currentSlot = self.JokerSlotList[jokerIndex]
        local leftSlot = self.JokerSlotList[jokerIndex - 1]
        if not currentSlot or not leftSlot then
            break
        end

        leftJoker.transform:SetParent(currentSlot.tran, true)
        leftJoker.transform.localPosition = bee.v3zero
        self.JokerList[jokerIndex] = leftJoker
        leftJoker.index = leftJoker.index + 1
        self.JokerList[jokerIndex - 1] = jokerCls
        jokerIndex = jokerIndex - 1
        jokerCls.index = jokerIndex
        BaseCardUtil:PlayAniState(leftJoker.ani, Bal.BaseCardAni.huanpaizuo, true)
        Game:playSound("ui_tab_switch_1_1")

        BalBattleModel:exchangeJoker(jokerCls.data.uid, jokerCls.index)
    end

    while jokerIndex < #self.JokerList do
        local rightJoker = self.JokerList[jokerIndex + 1]
        if not rightJoker or jokerTran.position.x <= rightJoker.transform.position.x or rightJoker.data.uid == 0 then
            break
        end

        local currentSlot = self.JokerSlotList[jokerIndex]
        local rightSlot = self.JokerSlotList[jokerIndex + 1]
        if not currentSlot or not rightSlot then
            break
        end

        rightJoker.transform:SetParent(currentSlot.tran, true)
        rightJoker.transform.localPosition = bee.v3zero
        self.JokerList[jokerIndex] = rightJoker
        rightJoker.index = rightJoker.index - 1
        self.JokerList[jokerIndex + 1] = jokerCls
        jokerIndex = jokerIndex + 1
        jokerCls.index = jokerIndex
        BaseCardUtil:PlayAniState(rightJoker.ani, Bal.BaseCardAni.huanpaiyou, true)
        Game:playSound("ui_tab_switch_1_1")

        BalBattleModel:exchangeJoker(jokerCls.data.uid, jokerCls.index)
    end
end

--归位
function P:moveToSolt(index)
    local jokerCls = self.JokerList and self.JokerList[index]
    local slot = self.JokerSlotList and self.JokerSlotList[index]
    if not jokerCls or not slot or not slot.tran then
        return
    end

    jokerCls.tweening = true
    local jokerTran = jokerCls.transform
    local startPos = jokerTran.position
    local endPos = slot.tran.position

    bee.tween():toVector(startPos, endPos, 0.25, function(v)
        jokerTran.position = v
    end):onComplete(function()
        jokerTran:SetParent(slot.tran, true)
        jokerTran.localPosition = bee.v3zero
        jokerCls.tweening = false
        Game:playSound("ui_tab_switch_2")
    end)
    BalBattleModel:changeJokerSeat()
end

--刷新奖励
function P:refreshRewardItem(data, item, isInit, index)
    local aniRoot = self:find("Ani_root", item)
    local propItem = self:find("Ani_root/item", item)
    local frame = self:find("common_item_grid_s_06", propItem)
    local icon = self:find("icon", propItem)
    local num = self:find("num", propItem)
    local claimable = self:find("Claimable", propItem)
    local claimed = self:find("Claimed", propItem)
    local progress = self:find("Ani_root/halloween_joker_main_slider_fg", item)
    local unlockPoint = self:find("Ani_root/halloween_joker_main_slider_bg_02", item)
    local clearedPoint = self:find("Ani_root/halloween_joker_main_slider_fg_01", item)
    local curLevelPoint = self:find("Ani_root/halloween_joker_main_slider_fg_02", item)
    local indexText = self:find("Ani_root/text", item)

    if isInit then
        self:once(0.1 * (index - 1), function()
            item:SetActive(true)
            self:playAnimator("UI_1_HalloweenJoker_item", aniRoot)
        end)
        item:SetActive(false)
    else
        self:playAnimator("UI_1_HalloweenJoker_item_idle", aniRoot)
        item:SetActive(true)
    end

    local propCfg = tpl_props[data.rewards[1]]
    bee.setIcon(frame, string.format("Common[common_item_grid_s_%02d]", propCfg.quality + 1))
    bee.setIcon(icon, propCfg.icon)
    bee.setText(num, _N2(data.rewards[2]))
    bee.setText(indexText, data.endless and "∞" or tostring(data.index))

    bee.addClick(propItem, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(data.rewards[1], true), target = propItem})
    end, true)

    if data.id < BalBattleModel.curLevel then
        claimable:SetActive(false)
        claimed:SetActive(true)
        progress:SetActive(true)
        clearedPoint:SetActive(true)
        unlockPoint:SetActive(false)
        curLevelPoint:SetActive(false)
    elseif data.id == BalBattleModel.curLevel then
        claimable:SetActive(true)
        claimed:SetActive(false)
        progress:SetActive(false)
        clearedPoint:SetActive(false)
        unlockPoint:SetActive(false)
        curLevelPoint:SetActive(true)
    else
        claimable:SetActive(false)
        claimed:SetActive(false)
        progress:SetActive(false)
        clearedPoint:SetActive(false)
        unlockPoint:SetActive(true)
        curLevelPoint:SetActive(false)
    end
end

--定位关卡进度
function P:jumpToCurReward()
    if self.curRewardIndex then
        local item = self.RewardList._items[self.curRewardIndex]
        local viewportWidth = self.RewardList._listSize.x
        local itemCenter = item.pos + item.w / 2
        local maxScroll = math.max(0, self.RewardList._size.x - viewportWidth)
        if itemCenter > maxScroll + viewportWidth / 2 then
            self.RewardList:moveToYItem(#self.RewardList._items, false, item.w / 2, nil, false)
        elseif itemCenter > viewportWidth / 2 then
            local targetScroll = math.min(
                maxScroll,
                math.max(0, itemCenter - viewportWidth / 2)
            )
            local baseScroll = math.min(item.pos, maxScroll)
            self.RewardList:moveToYItem(self.curRewardIndex, false, targetScroll - baseScroll, nil, false)
        else
            self.RewardList:moveToYItem(1, false, nil, nil, false)
        end
    end
    self.RewardList:refreshUi(true)
end

--关闭鬼牌详情
function P:closeJokerInfo(jokerCls)
    self.JokerInfoMask:SetActive(false)

    if jokerCls then
        BaseCardUtil:SwitchCardSelecting(jokerCls, true)
    else
        for _,v in pairs(self.JokerList) do
            if v.selecting then
                BaseCardUtil:SwitchCardSelecting(v)
                break
            end
        end
    end
end

--解锁提示
function P:unlockTip(index)
    local actionTime = ThemeModel:getStartTime()
    if actionTime <= 0 then
        return
    end

    local openDay = ThemeModel:getOpenDay() + 1
    local seatCfg = tpl_fate_seat[index]
    local unlockDay = seatCfg.day or 0
    if unlockDay > openDay then
        UiManager:showToast(_F("TAB_JOKER_DEC_29", unlockDay - openDay))
    end
end

function P:evt_balatroGameStart()
    Game:playSound("sound_balatro_enter")
    UiManager:showUI("LoadingLayer", {cb = function()
        bee.enterScene("GameScene", {onEnter = function()
            UiManager:showUI("HalloweenJoker")
        end})
    end})
end

--引导
function P:halloweenJokerGuide()
    GuideManager:startSystemGuide(24001, 0.65)
end


return P