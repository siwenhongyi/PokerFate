local P = class("HalloweenJoker", UiFullView)

function P:onAwake()
    P.super.onAwake(self)
    self.inBalatroGame = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.Top = self:find("Top", self.AnimRoot)
    self.Left = self:find("Left", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.Mask = self:find("Mask", self.AnimRoot)
    self.Mask:SetActive(false)

    self.JokerPoint = self:find("JokerCardList", self.Top)
    self.PokerPoint = self:find("PokerPoint", self.Center)
    self.DisplayArea = self:find("DisplayArea", self.Center)
    self.DisplayContent = self:find("DisplayArea/Content", self.Center)
    self.PokerBacks = self:find("PokerBacks", self.RightBottom)
    self.PokerBackList = {}
    self.decreaseNum = 0

    self.ScoreInfo = self:find("OverallRating", self.Top)
    self.ScoreProgress = self:find("Slider/halloween_joker_slider_fg", self.ScoreInfo):GetComponent("Image")
    self.ScoreValue = self:find("Value", self.ScoreInfo):GetComponent("Text")

    self.CardTypeInfo = self:find("Integral", self.Top)
    self.CardTypePart = {
        root = self:find("CardTypeLv", self.CardTypeInfo):GetComponent("RectTransform"),
        name = self:find("CardTypeLv/CardType", self.CardTypeInfo),
        lv = self:find("CardTypeLv/Level", self.CardTypeInfo),

        chipRoot = self:find("Chip", self.CardTypeInfo),
        powerRoot = self:find("Power", self.CardTypeInfo),
        chip = self:find("Chip/Value", self.CardTypeInfo):GetComponent("Text"),
        power = self:find("Power/Value", self.CardTypeInfo):GetComponent("Text"),
        fireFx = false,
        chipFx = self:find("Chip/bg_gacha_halloween_02_fire", self.CardTypeInfo),
        powerFx = self:find("Power/bg_gacha_halloween_03_fire", self.CardTypeInfo),
    }

    bee.addClick(self:find("OrderButton", self.Left), function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HalloweenCard")
        bee.logEvent("joker-info", 2, BalBattleModel.curLevel)
    end)
    
    self.BottomAni = self:find("AniRoot", self.Bottom)
    self.DisplayCount = self:find("DisplayCount", self.BottomAni):GetComponent("Text")
    self.RemainCount = self:find("RemainCount", self.RightBottom):GetComponent("Text")

    self.TipView = self:find("TipView", self.AnimRoot)
    self.tipList = {}

    self.pokerItemList = {}
    self.jokerItemList = {}
    self.playPokerItemList = {}

    self._scale = 1

    self.jokerPosList = {}
    --鬼牌详情
    self.JokerInfoMask = self:find("InfoMask", self.Top)
    bee.addClick(self.JokerInfoMask, function()
        self:closeJokerInfo()
    end)
    
    bee.addClick(self:find("PlayButton", self.BottomAni), function ()
        self:playEvent()
    end)
    self.PlayBtnText = self:find("PlayButton/Text", self.BottomAni)
    bee.addClick(self:find("FoldButton", self.BottomAni), function ()
        self:foldEvent()
    end)
    self.FoldBtnText = self:find("FoldButton/halloween_button_02/Text", self.BottomAni)
    self.FoldBtnGrayText = self:find("FoldButton/halloween_button_02_gray/Text", self.BottomAni)

    self.pointPart = self:find("Sort/Point", self.BottomAni)
    self.suitPart = self:find("Sort/Suit", self.BottomAni)
    bee.addClick(self:find("Button", self.pointPart), function ()
        self:suitSort()
        Game:playSound("ui_dealing_cards_2")
        self.pointPart:SetActive(false)
        self.suitPart:SetActive(true)
        bee.logEvent("joker-ingame-sort", BalBattleModel.curLevel, 2)
    end)
    bee.addClick(self:find("Button", self.suitPart), function ()
        self:pointSort()
        Game:playSound("ui_dealing_cards_2")
        self.pointPart:SetActive(true)
        self.suitPart:SetActive(false)
        bee.logEvent("joker-ingame-sort", BalBattleModel.curLevel, 1)
    end)
    self:setSortBtns()

    bee.addClick(self:find("BackButton", self.LeftTop), function ()
        Game:playSound("ui_button_confirm")
        self:onBtClose()
    end)

    self.bottomMoveTime = 0.4
end

function P:onShow()
    self:halloweenJokerGameGuide()

    BalBattleModel:initBattleData()
    BalBattleModel:roundStart()
    self:initJoker()
    self:showCardType()
    self:refreshTargetScore()
    self:refreshPlayCount()
    self:refreshFoldCount()
    self:initPokerBack()
    self:dealPoker()
    self.CardTypePart.fireFx = false
end

function P:afterShow()
    TournamentModel:refreshMatchingTip()
end

function P:initPokerBack()
    local count = self.PokerBacks.transform.childCount
    for i = 1, count do
        local pokerBack = self.PokerBacks.transform:GetChild(i - 1)
        local cardBackImage = DecorationModel:getCurCardBackImage(BalBattleModel:getScheme()) or nil
        bee.setIcon(pokerBack, cardBackImage)
        table.insert(self.PokerBackList, pokerBack)
    end
    self.decreaseNum = math.round(13 * 4 / count)
end

--#region poker

--发牌
function P:dealPoker()
    local datas = clone(BalBattleModel.displayPokerList)
    self:addDisplayCards(datas)
end
--补牌
function P:evt_BalReplenishPoker(datas)
    self:addDisplayCards(datas)
end
--增加手牌
function P:addDisplayCards(datas)
    self.Mask:SetActive(true)
    local count = table.nums(datas)
    for i = 1, count do
        local index = i
        self:once((index - 1) * 0.1, function ()
            local data = datas[index]
            local poker = bee.createObj("views/Halloween/HalloweenCardPoker")
            poker.transform:SetParent(self.PokerPoint.transform, false)
            poker.transform.localPosition = bee.v3zero
            poker.transform.localScale = bee.v3one * 0.85
            local pokerCls = ObjectPool:getCls(poker)
            pokerCls:setData(data)

            self:setEventTrigger(pokerCls)
            table.insert(self.pokerItemList, pokerCls)

            PokerUtil:SortDisplayPoker(self.pokerItemList)
            self:setIdlePokerPos()

            local sign = false
            for _,v in ipairs(self.pokerItemList) do
                if v.data.uid == pokerCls.data.uid then
                    sign = true
                else
                    if v and BaseCardUtil:isPlayOver(v.ani, Bal.BaseCardAni.fapai) then
                        BaseCardUtil:PlayAniState(v.ani, sign and Bal.BaseCardAni.paixuyou or Bal.BaseCardAni.paixuzuo, true)
                    end
                end
            end

            local endPos = poker.transform.localPosition
            poker.transform.position = self.PokerBacks.transform.position
            local strPos = poker.transform.localPosition
            local pokerCount = table.nums(self.pokerItemList)

            BaseCardUtil:PlayAniState(pokerCls.ani, Bal.BaseCardAni.fapai, true)
            Game:playSound("ui_card_turn")
            bee.tween():toFloat(0, 1, 0.2, function(v)
                poker.transform.localPosition = bee.v3Lerp(strPos, endPos, v)
                local cacheCount = table.nums(self.pokerItemList)
                if pokerCount ~= cacheCount then
                    endPos = self:getIdelPokerPos(pokerCls.data.uid)
                end
            end):onComplete(function()
                poker.transform.localPosition = self:getIdelPokerPos(pokerCls.data.uid)
                if index == count then
                    self.Mask:SetActive(false)
                end
            end)

            self:refreshDisplayCount()
            self:refreshRemainCount()

            self:refreshPokerBack(count, index)
        end)
    end
end

--扑克事件设置
function P:setEventTrigger(poker)
    if poker.handCardEventBound then
        return
    end

    poker.handCardEventBound = true
    poker.btn.onDown:AddListener(function ()
        self.handCardDragSuppressPointerId = nil
    end)
    poker.btn.onClick:AddListener(function (_, eventData)
        if eventData and self.handCardDragPointerId == eventData.pointerId then
            return
        end
        if eventData and self.handCardDragSuppressPointerId == eventData.pointerId then
            self.handCardDragSuppressPointerId = nil
            return
        end
        PokerUtil:ClickHandCard(poker, true)
        self:showCardType()
    end)
    poker.btn.onBeginDrag:AddListener(function (_, eventData)
        self:onHandCardBeginDrag(poker, eventData)
    end)
    poker.btn.onDrag:AddListener(function (_, eventData)
        self:onHandCardDrag(eventData)
    end)
    poker.btn.onEndDrag:AddListener(function (_, eventData)
        self:onHandCardEndDrag(eventData)
    end)
end

function P:onHandCardBeginDrag(poker, eventData)
    self.handCardDragPointerId = eventData.pointerId
    self.handCardDragStartPoker = poker
    self.handCardDragLastPoker = nil
    self:toggleHandPokerByDrag(poker)
end

function P:onHandCardDrag(eventData)
    local deltaX = eventData.delta.x

    local hitObject = eventData.pointerCurrentRaycast.gameObject
    if bee.isNull(hitObject) then
        return
    end

    local hitTransform = hitObject.transform
    for _, poker in ipairs(self.pokerItemList) do
        if hitTransform == poker.node.transform or hitTransform:IsChildOf(poker.node.transform) then
            local lastPokerIndex
            local startPokerIndex
            for i, handPoker in ipairs(self.pokerItemList) do
                if handPoker == self.handCardDragLastPoker then
                    lastPokerIndex = i
                end
                if handPoker == self.handCardDragStartPoker then
                    startPokerIndex = i
                end
            end

            local isReturningToStart = lastPokerIndex and startPokerIndex
                and ((lastPokerIndex < startPokerIndex and deltaX > 0)
                    or (lastPokerIndex > startPokerIndex and deltaX < 0))
            if self.handCardDragLastPoker ~= poker
                and isReturningToStart
                and self.handCardDragLastPoker ~= self.handCardDragStartPoker
                and self.handCardDragLastPoker.selecting then
                self:toggleHandPokerSelection(self.handCardDragLastPoker)
            end
            if poker == self.handCardDragStartPoker then
                self.handCardDragLastPoker = poker
            else
                self:toggleHandPokerByDrag(poker)
            end
            return
        end
    end
end

function P:onHandCardEndDrag(eventData)
    self.handCardDragPointerId = nil
    self.handCardDragStartPoker = nil
    self.handCardDragLastPoker = nil
    self.handCardDragSuppressPointerId = eventData.pointerId
end

function P:toggleHandPokerByDrag(poker)
    if self.handCardDragLastPoker == poker then
        return
    end

    self.handCardDragLastPoker = poker
    self:toggleHandPokerSelection(poker)
end

function P:toggleHandPokerSelection(poker)
    local wasSelecting = poker.selecting
    PokerUtil:ClickHandCard(poker, true)
    if poker.selecting ~= wasSelecting then
        self:showCardType()
    end
end

function P:playEvent()
    if BalBattleModel:getRemainPlayCount() <= 0 then
        return
    end

    self.playPokerItemList = self:getSelectingPoker()
    if next(self.playPokerItemList) == nil then
        UiManager:showToast(_T("TAB_JOKER_DEC_7"))
        return
    end

    self.Mask:SetActive(true)
    self:bottomAni(true)
    local index = 0
    for _,v in pairs(self.playPokerItemList) do
        index = index + 1
        self:once((index - 1) * 0.1 + self.bottomMoveTime, function ()
            BalBattleModel:removeDisplayPoker(v.data.uid)
            self:refreshDisplayCount()
            BaseCardUtil:PlayAniState(v.ani, Bal.BaseCardAni.chupai, true)
            Game:playSound("ui_card_turn")

            local tran = v.transform
            tran:SetParent(self.DisplayArea.transform, true)
            local startPos = tran.localPosition
            local endPos = bee.v3(0, -30, 0)
            bee.tween():toVector(startPos, endPos, 0.2, function(v)
                tran.localPosition = v
            end):onComplete(function()
                tran:SetParent(self.DisplayContent.transform, false)
            end)
            BaseCardUtil:selectDownEx(v)

            local displayCount = table.nums(self.pokerItemList)
            local sign = false
            for i = displayCount, 1, -1 do
                local poker = self.pokerItemList[i]
                if v.data.uid == poker.data.uid then
                    sign = true
                else
                    BaseCardUtil:PlayAniState(poker.ani, sign and Bal.BaseCardAni.paixuyou or Bal.BaseCardAni.paixuzuo, true)
                end
            end

            table.removebyvalue(self.pokerItemList, v)
            self:setIdlePokerPos()
        end)
    end

    BalBattleModel:playCard()
    self:refreshPlayCount()
    BalBattleModel:sortOutCtrlData(1)
    self:once(0.1 * #self.playPokerItemList + 0.5 + self.bottomMoveTime, function ()
        local scoringList = {}
        local subIndex = 0
        for _,v in pairs(self.playPokerItemList) do
            if table.keyof(BalBattleModel.curScoringList, v.data.uid) ~= nil then
                subIndex = subIndex + 1
                table.insert(scoringList, v.data)
                self:once((subIndex - 1) * 0.1, function ()
                    BaseCardUtil:PlayAniState(v.ani, Bal.BaseCardAni.xuanzhong, true)
                    BaseCardUtil:selectUpEx(v)
                end)
            end
        end
        self:once(0.1 * #scoringList + 0.2, function ()
            BalSkillUtil:showCardStage(scoringList, BalBattleModel.ownedJokerList)
        end)
    end)
    bee.logEvent("joker-ingame-play", BalBattleModel.curLevel)
end
function P:foldEvent()
    if BalBattleModel:getRemainFoldCount() <= 0 then
        UiManager:showToast(_T("TAB_JOKER_DEC_23"))
        return
    end

    local foldList = self:getSelectingPoker()
    if next(foldList) == nil then
        UiManager:showToast(_T("TAB_JOKER_DEC_7"))
        return
    end

    self.Mask:SetActive(true)
    BalBattleModel:foldCard()
    self:refreshFoldCount()
    BalBattleModel:sortOutCtrlData(2)
    BalBattleModel:clearSelectingCardDic()
    self:delCardAction(foldList)

    if BalBattleModel:getRemainFoldCount() == 0 then
        self:find("FoldButton/halloween_button_02_gray", self.BottomAni):SetActive(true)
    end
    bee.logEvent("joker-ingame-discard", BalBattleModel.curLevel)
end
--获取按卡牌排序选中的手牌
function P:getSelectingPoker()
    local list = {}
    for _,v in pairs(self.pokerItemList) do
        for _,sv in pairs(BalBattleModel.selectingCardDic) do
            if v.data.uid == sv.uid then
                table.insert(list, v)
                break
            end
        end
    end
    return list
end
--移除卡牌事件
function P:delCardAction(delList)
    if #delList <= 0 then
        self:once(0.3, function ()
            self:recoveryPokerOver(Bal.RecoveryPokerType.Fold)
        end)
        return
    end

    local delCard = delList[1]
    table.remove(delList, 1)

    Game:playSound("ui_card_turn")
    local delPokerData = BalBattleModel:foldPoker(delCard.data.uid)
    BalSkillUtil:foldPoker(delPokerData)
    self:refreshDisplayCount()

    local displayCount = table.nums(self.pokerItemList)
    local sign = false
    for i = displayCount, 1, -1 do
        local poker = self.pokerItemList[i]
        if delCard.data.uid == poker.data.uid then
            sign = true
            table.remove(self.pokerItemList, i)
            BaseCardUtil:DeletePokerAni(poker)
            self:setIdlePokerPos()
        else
            BaseCardUtil:PlayAniState(poker.ani, sign and Bal.BaseCardAni.paixuyou or Bal.BaseCardAni.paixuzuo, true)
        end
    end

    self:once(Bal.RecoveryPokerTime, function() self:delCardAction(delList) end)
end


--回收结束
function P:recoveryPokerOver(type, over)
    self.Mask:SetActive(false)

    if over then
        BalBattleModel:gameOver()
    else
        BalBattleModel:newHand()
        self:showCardType()
    end

    -- local toNext = BalBattleModel:checkToNext()
    -- if toNext then
    -- end
end

function P:showCardType()
    local data = BalatroRule:CheckCardType(BalBattleModel.selectingCardDic)
    local cardType = data and data.type or nil
    bee.setText(self.CardTypePart.name, cardType and _T(POKER_TYPE_NAME[cardType]) or "??")
    bee.setText(self.CardTypePart.lv, _F("LAB_LEVEL_TEXT_5", (cardType and BalBattleModel.cardTypeLv[cardType] or "??")))
    CU.Canvas.ForceUpdateCanvases()
    CU.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(self.CardTypePart.root)
    BalBattleModel:setChipAndPower(cardType)
    self:refreshChipAndPower()
end
function P:refreshChipAndPower(playAni, isChip)
    if playAni then
        self:once(0.1, function ()
            self.CardTypePart.chip.text = BalBattleModel.curChip
            self.CardTypePart.power.text = BalBattleModel.curPower
        end)
        AnimationMgr:playAnim(isChip and self.CardTypePart.chipRoot or self.CardTypePart.powerRoot, "BalatroChipAndPower_jump")
    else
        self.CardTypePart.chip.text = BalBattleModel.curChip
        self.CardTypePart.power.text = BalBattleModel.curPower
    end
end

function P:refreshTargetScore(playAni, score)
    local tarVal = BalBattleModel.matchingScore
    --tarVal = math.max(0, tarVal)
    local cacheVal = 0
    if playAni then
        bee.tween():toFloat(score, tarVal, 0.75, function (v)
            cacheVal = math.floor(v)
            bee.setText(self.ScoreValue, cacheVal .. "/" .. BalBattleModel.targetScore)
            local amout = 0
            if tarVal <= BalBattleModel.targetScore then
                amout = cacheVal / BalBattleModel.targetScore
            else
                local strRatio = score / BalBattleModel.targetScore
                local cacheVal = tarVal - score
                local cacheRatio = (v - score) / cacheVal
                amout = strRatio + (1 - strRatio) * cacheRatio
            end
            self.ScoreProgress.fillAmount = amout
        end)
    else
        bee.setText(self.ScoreValue, tarVal .. "/" .. BalBattleModel.targetScore)
        self.ScoreProgress.fillAmount = tarVal / BalBattleModel.targetScore
    end
end

--卡牌表现
function P:evt_BalDisplayCardEffect(data)
    if data.poker ~= nil then
        self:showPokerEffect(data)
    end
    if data.joker ~= nil then
        self:showJokerEffect(data)
    end

    if BalBattleModel.curChip * BalBattleModel.curPower > BalBattleModel.targetScore then
        if not self.CardTypePart.fireFx then
            self.CardTypePart.fireFx = true
            self.CardTypePart.chipFx:SetActive(true)
            self.CardTypePart.powerFx:SetActive(true)
            Game:playSound("sound_balatro_fire")
        end
    end
end
function P:showPokerEffect(data)
    local pokerItem = nil
    for _,v in pairs(self.playPokerItemList) do
        if v.data.uid == data.poker.uid then
            pokerItem = v
            break
        end
    end
    if pokerItem == nil then
        return
    end
    BaseCardUtil:PlayAniState(pokerItem.ani, Bal.BaseCardAni.jiafen, true)

    if data.effect.weaken then
        --虚弱提示
        local tip = self:getPlayTip()
        tip:setInfo(nil, "虚弱")
        self:showTip(tip, pokerItem, 1)
        return
    end
    if data.effect.redSeal then
        --再来一次
        local tip = self:getPlayTip()
        tip:setInfo(nil, "再来一次")
        self:showTip(tip, pokerItem, 1)
        return
    end

    self:checkShowTip(data.effect, pokerItem, 1)
end
function P:showJokerEffect(data)
    local jokerItem = nil
    for _,v in pairs(self.jokerItemList) do
        if v.data.uid == data.joker.uid then
            jokerItem = v
            break
        end
    end
    if jokerItem == nil then
        return
    end
    BaseCardUtil:PlayAniState(jokerItem.ani, Bal.BaseCardAni.jiafen, true)

    self:checkShowTip(data.effect, jokerItem, 2)
end
function P:checkShowTip(effect, cardItem, type)
    if effect.rewardId == Bal.ParameterType.Chip or effect.rewardId == Bal.ParameterType.Power or effect.rewardId == Bal.ParameterType.MulPower then
        local rewardCount = effect.rewardCount
        if effect.rewardId == Bal.ParameterType.MulPower then
            rewardCount = rewardCount / BalSkillUtil.ratio
        end
        local tip = self:getPlayTip()
        tip:setInfo(effect.rewardId, rewardCount)
        self:showTip(tip, cardItem, type)
        if type == 1 then
            Game:playSound("sound_balatro_score")
        else
            if effect.rewardId == Bal.ParameterType.Chip then
                Game:playSound("sound_balatro_add")
            else
                Game:playSound("sound_balatro_mult")
            end
        end
        self:refreshChipAndPower(true, effect.rewardId == Bal.ParameterType.Chip)
    elseif effect.rewardId == Bal.ParameterType.Gold then
        local tip = self:getPlayTip()
        tip:setInfo(effect.rewardId, effect.rewardCount)
        self:showTip(tip, cardItem, type)
    end
end
function P:showTip(tip, cardItem, type)
    tip:showTip()
    tip.transform.position = cardItem.transform.position
    local y = type == 1 and 200 or -200
    tip.transform.localPosition = tip.transform.localPosition + bee.v3(0, y, 0)
end

--事件表现结束
function P:evt_BalTriggerEventOver(info)
    if info.effType == Bal.DisplayType.Scoring then
        BalBattleModel:clearSelectingCardDic()
        --计分
        self:refreshTargetScore(true, info.score)
        --出牌后回收卡牌
        self:once(1.2, function()
            self:recoveryPlayedPoker()
        end)
    end
end

--出牌后回收卡牌
function P:recoveryPlayedPoker()
    local scoringList = {}
    local subIndex = 0
    for _,v in pairs(self.playPokerItemList) do
        if table.keyof(BalBattleModel.curScoringList, v.data.uid) ~= nil then
            subIndex = subIndex + 1
            table.insert(scoringList, v.data)
            self:once((subIndex - 1) * 0.1, function ()
                BaseCardUtil:PlayAniState(v.ani, Bal.BaseCardAni.xuanzhongchehui, true)
                BaseCardUtil:selectDownEx(v)
            end)
        end
    end

    local index = 0
    self:once(0.1 * #scoringList + 0.2, function ()
        for _,v in pairs(self.playPokerItemList) do
            index = index + 1
            self:once(index * 0.1, function ()
                Game:playSound("ui_card_turn")
                BaseCardUtil:DeletePokerAni(v)
            end)
        end
        self:once(0.1 * #self.playPokerItemList + 0.2, function ()
            local isGameOver = BalBattleModel:checkGameOver()
            local floatTime = 0
            if not isGameOver then
                floatTime = self.bottomMoveTime
                self:bottomAni(false)
            end

            self:once(floatTime, function ()
                self.playPokerItemList = {}
                self:recoveryPokerOver(Bal.RecoveryPokerType.Played, isGameOver)
            end)
        end)
    end)
end

--排序
function P:setSortBtns()
    self.pointPart.gameObject:SetActive(BalBattleModel.sortType == Bal.PokerSortType.Point)
    self.suitPart.gameObject:SetActive(BalBattleModel.sortType == Bal.PokerSortType.Suit)
end

function P:pointSort()
    BalBattleModel.sortType = Bal.PokerSortType.Point
    self:sortDisplayPoker()
    -- PokerUtil:SortDisplayPoker(self.pokerItemList)
    self:setIdlePokerPos()
end
function P:suitSort()
    BalBattleModel.sortType = Bal.PokerSortType.Suit
    self:sortDisplayPoker()
    -- PokerUtil:SortDisplayPoker(self.pokerItemList)
    self:setIdlePokerPos()
end

function P:sortDisplayPoker()
    local cacheList = {}
    for _,v in pairs(self.pokerItemList) do
        table.insert(cacheList, v.data.uid)
    end

    PokerUtil:SortDisplayPoker(self.pokerItemList)
    local count = table.nums(self.pokerItemList)
    local difList = {}
    for i = 1, count do
        local poker = self.pokerItemList[i]
        if poker.uid ~= cacheList[i] then
            local lor = false
            for di = 1, count do
                if self.pokerItemList[di].data.uid == cacheList[i] then
                    lor = di < i
                    break
                end
            end
            table.insert(difList, {poker = poker, lor = lor})
        end
    end
    
    for _,v in pairs(difList) do
        local aniStr = v.lor and Bal.BaseCardAni.huanpaiyou or Bal.BaseCardAni.huanpaizuo
        BaseCardUtil:PlayAniState(v.poker.ani, aniStr, true)
    end
end

function P:setIdlePokerPos()
    local count = #self.pokerItemList
    local startX = -((count - 1) * (175 / 2 + 5))
    for i, poker in pairs(self.pokerItemList) do
        poker.transform.localPosition = bee.v3(startX + (i - 1) * (175 + 10), 0, 0)
    end
end

function P:getIdelPokerPos(uid)
    -- PokerUtil:SortDisplayPoker(self.pokerItemList)
    for i, poker in ipairs(self.pokerItemList) do
        if poker.data.uid == uid then
            local count = #self.pokerItemList
            local startX = -((count - 1) * (175 / 2 + 5))
            return bee.v3(startX + (i - 1) * (175 + 10), 0, 0)
        end
    end
    return bee.v3zero
end

--#endregion

--#region joker

function P:initJoker()
    local index = 0
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        index = index + 1
        local joker = bee.createObj("views/Halloween/HalloweenCardJoker")
        joker.transform:SetParent(self.JokerPoint.transform, false)
        joker.transform.localPosition = bee.v3zero
        joker.transform.localScale = bee.v3one * 0.5
        local jokerCls = ObjectPool:getCls(joker)
        jokerCls:setData(v)
        jokerCls.index = index
        self.jokerItemList[index] = jokerCls
        jokerCls.btn.onClick:AddListener(function () self:showJokerDetail(jokerCls) end)
        jokerCls.btn.onBeginDrag:AddListener(function (go, eventData) self:onBeginDrag(jokerCls, eventData) end)
        jokerCls.btn.onDrag:AddListener(function (go, eventData) self:onDrag(jokerCls, eventData) end)
        jokerCls.btn.onEndDrag:AddListener(function (go, eventData) self:onEndDrag(jokerCls, eventData) end)
        -- jokerCls.btn.onPress:AddListener(function () self:onLongPress(jokerCls) end)
        jokerCls.btn.onDown:AddListener(function () self:onDown(jokerCls) end)
        jokerCls.btn.onUp:AddListener(function () self:onUp(jokerCls) end)
        jokerCls:setRefresh(false)
    end
    self:setJokerPos()
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

    for _,v in pairs(self.jokerItemList) do
        if v.selecting then
            BaseCardUtil:SwitchCardSelecting(v)
            v.transform:SetSiblingIndex(v.index - 1)
            break
        end
    end

    BaseCardUtil:SwitchCardSelecting(jokerCls, true)
    jokerCls.transform:SetAsLastSibling()
    JokerUtil:showJokerDetail(jokerCls, self.JokerInfoMask)
end

-- function P:onLongPress(jokerCls)
--     if jokerCls.draging then
--         return
--     end
--     if not jokerCls.longPress then
--         jokerCls.longPress = true
--         jokerCls.transform:SetAsLastSibling()
--         BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.changan)
--     end
-- end
function P:onBeginDrag(jokerCls, eventData)
    if self.JokerInfoMask.activeSelf then
        self:closeJokerInfo()
    end

    jokerCls.draging = true
    jokerCls.transform:SetAsLastSibling()
    BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.changan, true)
end
function P:onDrag(jokerCls, eventData)
    jokerCls.transform.localPosition = jokerCls.transform.localPosition + bee.v3(eventData.delta.x / self._scale, eventData.delta.y / self._scale, 0)
    self:checkMove(jokerCls)
end
function P:onEndDrag(jokerCls, eventData)
    jokerCls.draging = false
    self:moveToTarget(jokerCls.index)
    BaseCardUtil:PlayAniState(jokerCls.ani, Bal.BaseCardAni.daiji, true)
end
function P:onDown(jokerCls)
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

--移动
function P:checkMove(jokerCls)
    if not jokerCls or not jokerCls.transform or not jokerCls.index then
        return
    end

    local jokerTran = jokerCls.transform
    local jokerIndex = jokerCls.index
    local jokerCount = #self.jokerItemList

    while jokerIndex > 1 do
        local leftJoker = self.jokerItemList[jokerIndex - 1]
        local leftPos = self.jokerPosList[jokerIndex - 1]
        if not leftJoker or not leftPos or jokerTran.localPosition.x >= leftPos.x then
            break
        end

        local currentPos = self.jokerPosList[jokerIndex]
        if not currentPos then
            break
        end

        leftJoker.transform.localPosition = currentPos
        self.jokerItemList[jokerIndex] = leftJoker
        self.jokerItemList[jokerIndex - 1] = jokerCls
        leftJoker.index = jokerIndex
        jokerIndex = jokerIndex - 1
        jokerCls.index = jokerIndex
        BaseCardUtil:PlayAniState(leftJoker.ani, Bal.BaseCardAni.huanpaizuo, true)
        Game:playSound("ui_tab_switch_1_1")

        BalBattleModel:exchangeJoker(jokerCls.data.uid, jokerCls.index)
    end

    while jokerIndex < jokerCount do
        local rightJoker = self.jokerItemList[jokerIndex + 1]
        local rightPos = self.jokerPosList[jokerIndex + 1]
        if not rightJoker or not rightPos or jokerTran.localPosition.x <= rightPos.x then
            break
        end

        local currentPos = self.jokerPosList[jokerIndex]
        if not currentPos then
            break
        end

        rightJoker.transform.localPosition = currentPos
        self.jokerItemList[jokerIndex] = rightJoker
        self.jokerItemList[jokerIndex + 1] = jokerCls
        rightJoker.index = jokerIndex
        jokerIndex = jokerIndex + 1
        jokerCls.index = jokerIndex
        BaseCardUtil:PlayAniState(rightJoker.ani, Bal.BaseCardAni.huanpaiyou, true)
        Game:playSound("ui_tab_switch_1_1")

        BalBattleModel:exchangeJoker(jokerCls.data.uid, jokerCls.index)
    end
end

--归位
function P:moveToTarget(index)
    local jokerCls = self.jokerItemList and self.jokerItemList[index]
    local targetPos = self.jokerPosList and self.jokerPosList[index]
    if not jokerCls or not targetPos then
        return
    end

    jokerCls.tweening = true
    local jokerTran = jokerCls.transform
    local startPos = jokerTran.localPosition
    bee.tween():toVector(startPos, targetPos, 0.25, function(v)
        jokerTran.localPosition = v
    end):onComplete(function()
        jokerTran:SetParent(self.JokerPoint.transform, false)
        jokerTran.localPosition = targetPos
        jokerCls.tweening = false
        for jokerIndex, joker in ipairs(self.jokerItemList) do
            joker.transform:SetSiblingIndex(jokerIndex - 1)
        end
        Game:playSound("ui_tab_switch_2")
    end)
end

--排序
function P:setJokerPos()
    local count = #self.jokerItemList
    if count == 0 then
        return
    end

    self.jokerPosList = {}

    local cardWidth = 200
    local normalSpacing = 10
    local maxWidth = 1060
    local spacing = cardWidth + normalSpacing

    if count > 1 then
        spacing = math.min(spacing, (maxWidth - cardWidth) / (count - 1))
    end

    local startX = -((count - 1) * spacing) / 2
    for i, joker in ipairs(self.jokerItemList) do
        joker.transform.localPosition = bee.v3(startX + (i - 1) * spacing, 0, 0)
        table.insert(self.jokerPosList, joker.transform.localPosition)
    end
end

function P:closeJokerInfo(jokerCls)
    self.JokerInfoMask:SetActive(false)

    if jokerCls then
        BaseCardUtil:SwitchCardSelecting(jokerCls, true)
        jokerCls.transform:SetSiblingIndex(jokerCls.index - 1)
    else
        for _,v in pairs(self.jokerItemList) do
            if v.selecting then
                BaseCardUtil:SwitchCardSelecting(v)
                v.transform:SetSiblingIndex(v.index - 1)
                break
            end
        end
    end
end

--#endregion


--#region 提示

function P:getPlayTip()
    if table.nums(self.tipList) ~= 0 then
        local tipCls = self.tipList[1]
        table.remove(self.tipList, 1)
        tipCls.node:SetActive(true)
        return tipCls
    end

    local tip = bee.createObj("views/Balatro/BalatroPlayTip")
    tip.transform:SetParent(self.TipView.transform, false)
    tip:SetActive(true)
    return ObjectPool:getCls(tip)
end

function P:evt_BalPlayTipOver(data)
    table.insert(self.tipList, data.cls)
    data.cls.node:SetActive(false)
end

--#endregion

--刷新持牌数量
function P:refreshDisplayCount()
    self.DisplayCount.text = #BalBattleModel.displayPokerList .. "/" .. BalBattleModel.matchingKeepCardCount
end

--刷新牌组数量
function P:refreshRemainCount()
    self.RemainCount.text = #BalBattleModel.matchingRemainIdList .. "/" .. table.nums(BalBattleModel.matchingPokerDataDic)
end

--刷新出牌剩余次数
function P:refreshPlayCount()
    bee.setText(self.PlayBtnText, _F("TAB_JOKER_DEC_9", BalBattleModel:getRemainPlayCount()))
end

--刷新弃牌剩余次数
function P:refreshFoldCount()
    bee.setText(self.FoldBtnText, _F("TAB_JOKER_DEC_8", BalBattleModel:getRemainFoldCount()))
    bee.setText(self.FoldBtnGrayText, _F("TAB_JOKER_DEC_8", BalBattleModel:getRemainFoldCount()))
end

--刷新牌组
function P:refreshPokerBack(cNum, cIndex)
    local remain = #BalBattleModel.matchingRemainIdList + cNum - cIndex
    local total = table.nums(BalBattleModel.matchingPokerDataDic)
    local hideCount = math.round((total - remain) / self.decreaseNum)
    if remain > 0 then
        hideCount = math.min(hideCount, math.max(#self.PokerBackList - 1, 0))
    else
        hideCount = #self.PokerBackList
    end
    for i = 1, hideCount do
        if self.PokerBackList[i] then
            self.PokerBackList[i].gameObject:SetActive(false)
        end
    end
end

--底部动画
function P:bottomAni(sw)
    AnimationMgr:playAnim(self.Center, sw and "UI_1_HalloweenJokerCenter_down" or "UI_1_HalloweenJokerCenter_up")
    AnimationMgr:playAnim(self.BottomAni, sw and "UI_1_HalloweenJokerBottom_down" or "UI_1_HalloweenJokerBottom_up")
end

function P:onBtClose()
    UiManager:showUI("HalloweenHint", {
            text = _T("TAB_JOKER_DEC_5"),
            onSure = function()
                -- self:hideUI()
                -- BalBattleModel.playing = false
                self:unscheduleAll()
                BalSkillUtil:clearMarkSkill()
                BalSkillUtil:dispose()
                BalBattleModel:changeJokerSeat()
                BalBattleModel:returnMainView()
                bee.logEvent("joker-ingame-back", BalBattleModel.curLevel)
            end
        })

    -- UiManager:showTip({
    --     text = _T("TAB_JOKER_DEC_5"),
    --     onSure = function()
    --         -- self:hideUI()
    --         -- BalBattleModel.playing = false
    --         self:unscheduleAll()
    --         BalSkillUtil:clearMarkSkill()
    --         BalSkillUtil:dispose()
    --         BalBattleModel:changeJokerSeat()
    --         BalBattleModel:returnMainView()
    --         bee.logEvent("joker-ingame-back", BalBattleModel.curLevel)
    --     end
    -- })
end

--引导
function P:halloweenJokerGameGuide()
    GuideManager:startSystemGuide(24101, 0.65)
end

function P:evt_guide_balatro_select_poker()
    local poker = self.pokerItemList[1]
    if not poker then
        return
    end

    poker.node.name = "HalloweenJokerGuidePoker"
    poker.node:AddComponent(typeof(CU.UI.Button))
    bee.addClick(poker.node, function ()
        PokerUtil:ClickHandCard(poker, true)
        self:showCardType()

        poker.node.transform.localScale = bee.v3one * 0.85
        CU.GameObject.Destroy(poker.node:GetComponent("Button"))
    end)
    tpl_guide[24102].show_ui = {
        "HalloweenJoker/AnimRoot/Center/PokerPoint/" .. poker.node.name
    }
end

--模糊
function P:evt_uiBlur(flag, name)
    if name == self.__cname then
        return
    end

    P.super.evt_uiBlur(self, flag, name)

    local camera = bee.find("UIRoot/CameraRoot/UiCameraPost")
    if bee.isNull(camera) then
        return
    end

    local cameraComponent = camera:GetComponent("Camera")
    local postProcessLayer = camera:GetComponent("PostProcessLayer")
    local postProcessVolume = camera:GetComponent("PostProcessVolume")
    if not cameraComponent or not postProcessLayer or not postProcessVolume then
        return
    end

    if flag then
        if not self._popupUiCameraState then
            self._popupUiCameraState = {
                camera = cameraComponent.enabled,
                postProcessLayer = postProcessLayer.enabled,
                postProcessVolume = postProcessVolume.enabled,
            }
        end
        cameraComponent.enabled = true
        postProcessLayer.enabled = true
        postProcessVolume.enabled = true
    elseif not (self._inBlurs and next(self._inBlurs)) and self._popupUiCameraState then
        cameraComponent.enabled = self._popupUiCameraState.camera
        postProcessLayer.enabled = self._popupUiCameraState.postProcessLayer
        postProcessVolume.enabled = self._popupUiCameraState.postProcessVolume
        self._popupUiCameraState = nil
    end
end

return P