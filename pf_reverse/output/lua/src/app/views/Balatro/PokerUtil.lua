local P = {
    --排序类型
    sortType = Bal.PokerSortType.Point,
    --手牌起始位单位距离
    startPosUnitDis = -43,
    --出牌扑克排序间隔
    playedPokerInterval = 120,

    --扑克位置
    pokerPosDic = {},
    --扑克卡包内位置
    pokerInPackPosDic = {},

    --拖动差值
    dragDelta = nil,
}
PokerUtil = P


--扑克基础数据
function P:creatNewPokerData()
    local cardData = {
        --uid
        uid = 0,
        --卡类
        category = Bal.CardCategory.Poker,
        --身份id
        pid = 0,
        --所在位置
        -- place = B.CardPlaceType.None,
        --花色
        suit = 0,
        --点数
        point = 0,
        --运算值
        value = 0,
        --版本
        edition = 0,
        --增强
        enhance = 0,
        --蜡封
        seal = 0,
        --削弱
        weaken = false,
        --背卡
        backCard = false,
        --增值价格
        addedPrice = 0,
        --额外参数
        params = {
            extraChips = 0, --额外筹码
        },
    }
    return cardData
end

--创建初始牌组数据
function P:createDefaultPokerGroupData()
    local defaultPokerDic = {}
    for _,sv in pairs(Bal.PokerSuit) do
        for _,vv in pairs(Bal.PokerValue) do
            local data = self:creatNewPokerData()
            data.uid = BalBattleModel:getNewUid()
            data.suit = sv
            data.point = vv
            data.pid = tonumber(sv .. string.format("%02d", vv))
            data.value = Bal.PokerScore[vv]
            defaultPokerDic[data.uid] = data
        end
    end
    return defaultPokerDic
end

--创建卡牌Item
function P:createPokerCardItemByData(data, path)
    local card = bee.createObj(path or "views/Balatro/BalatroBaseCard")
    local cls = ObjectPool:getCls(card)
    cls:setData(data)
    -- card.idleSpeed = math.random(1, 3)
    return card
end

--从卡组内获得一张扑克牌
function P:getPokerItem(pokerData)
    local data
    if pokerData == nil then
        data = self:getPokerData()
    else
        data = self:getPokerData2(pokerData[1], pokerData[2])
    end
    if data == nil then return nil end
    local poker = self:createPokerCardItemByData(data)
    return poker
end
--从卡组内获得一张扑克数据
function P:getPokerData()
    local count = table.nums(BalBattleModel.matchingRemainIdList)
    if count == 0 then return end

    local index = BalBattleModel:GetRandom(0, count) + 1
    local data = BalBattleModel.matchingPokerDataDic[BalBattleModel.matchingRemainIdList[index]]
    table.remove(BalBattleModel.matchingRemainIdList, index)
    return data
end
--从卡组内获得一张指定花色和点数的扑克数据
function P:getPokerData2(suit, value)
    local key
    local data
    for k,v in pairs(BalBattleModel.matchingRemainIdList) do
        local cacheData = BalBattleModel.matchingPokerDataDic[v]
        if cacheData.suit == suit and cacheData.point == value then
            key = k
            data = cacheData
            break
        end
    end
    if key then
        table.remove(BalBattleModel.matchingRemainIdList, key)
    end
    return data
end

--生成一张新扑克牌数据
function P:createNewPokerData(point, suit)
    local pokerData
    --从可用的牌组内创建
    if point == nil and suit == nil then
        local pokerNum = table.nums(BalBattleModel.usablePokerCardData)
        local index = BalBattleModel:GetRandom(0, pokerNum) + 1
        pokerData = BalBattleModel.usablePokerCardData[index]
    else
        for _,v in pairs(BalBattleModel.usablePokerCardData) do
            if v.point == point and v.suit == suit then
                pokerData = v
                break
            end
        end
    end

    local data = self:creatNewPokerData()
    data.uid = BalBattleModel:getNewUid()
    data.suit = pokerData.suit
    data.point = pokerData.point
    data.value = pokerData.value
    local pokerConfigId = self:getPokerConfigId(data.suit, data.point)
    data.pokerConfigId = pokerConfigId
    return data
end

--生成一张商店扑克牌
function P:createNewGoodsPoker(strengthenable, point, suit)
    local data = self:createNewPokerData(point, suit)
    if strengthenable then
        data.edition = BalBattleModel:GetRandomEdition(false)
        data.enhance = BalBattleModel:GetRandomEnhance()
        data.seals = BalBattleModel:GetRandomSeal()
    end
    local poker = self:createPokerCardItemByData(data)
    return poker
end

--生成一张常规扑克牌
function P:createNewNormalPoker(strengthenId, point, suit)
    local data = self:createNewPokerData(point, suit)
    local config = tpl_[strengthenId]
    if config.type == Bal.CardStrengthenType.Edition then
        data.edition = strengthenId
    elseif config.type == Bal.CardStrengthenType.Enhance then
        data.enhance = strengthenId
    elseif config.type == Bal.CardStrengthenType.Seal then
        data.seals = strengthenId
    end
    local poker = self:createPokerCardItemByData(data)
    return poker
end


--点击手牌
function P:ClickHandCard(card, click)
    if BalBattleModel.forceSelectId == card.data.uid then
        if card.selecting then return end
    end

    local cardCount = table.nums(BalBattleModel.selectingCardDic)
    if cardCount == BalatroRule.limitPlayCardNum then
        if BalBattleModel.selectingCardDic[card.data.uid] == nil then
            UiManager:showToast(_T("TAB_JOKER_DEC_25"))
            return
        end
    end

    self:ClickIdlePoker(card, click)
    -- bee.emit("")
end

--点击扑克
function P:ClickIdlePoker(card, click)
    BaseCardUtil:SwitchCardSelecting(card, click)
    BalBattleModel.selectingCardDic[card.data.uid] = card.selecting and card.data or nil
end

--点击商店扑克
function P:ClickPokerInShop(card, click)
    BaseCardUtil:SwitchCardSelecting(card, click)

    if card.selecting then
        -- bee.emit("")

        card.tran:SetAsLastSibling()
        card.confirmTran.gameObject:SetActive(true)
    else
        card.confirmTran.gameObject:SetActive(false)
    end
end

--获得排序手牌
function P:SortDisplayPoker(list, sortType)
    if sortType == nil then
        sortType = BalBattleModel.sortType
    end
    if sortType == Bal.PokerSortType.Point then
        self:SortPokerByNumber(list)
    else
        self:SortPokerBySuit(list)
    end
end
--数值排序
function P:SortPokerByNumber(list)
    table.sort(list, function(a, b)
        if a.data.point == b.data.point then
            if a.data.suit == b.data.suit then
                return a.data.uid < b.data.uid
            else
                return a.data.suit > b.data.suit
            end
        else
            if a.data.point == 1 then
                return true
            elseif b.data.point == 1 then
                return false
            else
                return a.data.point > b.data.point
            end
        end
    end)
end
--花色排序
function P:SortPokerBySuit(list)
    table.sort(list, function(a, b)
        if a.data.suit == b.data.suit then
            if a.data.point == b.data.point then
                return a.data.uid < b.data.uid
            else
                if a.data.point == 1 then
                    return true
                elseif b.data.point == 1 then
                    return false
                else
                    return a.data.point > b.data.point
                end
            end
        else
            return a.data.suit > b.data.suit
        end
    end)
end

--牌组新增扑克牌
function P:AddNewPoker(pokerData, addInGroup)
    BalBattleModel:AddNewPoker(pokerData, addInGroup)
    BalSkillUtil:AddNewPoker(pokerData)
end
--牌组删除扑克牌
function P:DestroyPoker(pokerData)
    BalBattleModel:DestroyPoker(pokerData)
    BalSkillUtil:DestroyPoker(pokerData)
end

--将A扑克变成B扑克
function P:ChangeAIntoB(a, b)
    a.data.point = b.data.point
    a.data.value = b.data.value
    a.data.suit = b.data.suit
    a.data.edition = b.data.edition
    a.data.enhance = b.data.enhance
    a.data.seals = b.data.seals
    a.data.weaken = b.data.weaken

    a.icon.sprite = b.icon.sprite
    if b.data.edition == Bal.EditionType.Base then
        a.edition.gameObject:SetActive(false)
    else
        a.edition.sprite = b.edition.sprite
        a.edition.gameObject:SetActive(true)
    end
    if b.data.enhance == Bal.EnhanceType2.None then
        a.enhance.gameObject:SetActive(false)
    else
        a.enhance.sprite = b.enhance.sprite
        a.enhance.gameObject:SetActive(true)
    end
    if b.data.seals == Bal.SealType2.None then
        a.seal.gameObject:SetActive(false)
    else
        a.seal.sprite = b.seal.sprite
        a.seal.gameObject:SetActive(true)
    end
    a.invalid.gameObject:SetActive(a.data.weaken)
end

--给扑克增强
function P:EnhancePoker(pokerList, type)
    for _,v in pairs(pokerList) do
        v.data.enhance = type
        -- v.enhance.sprite = 
        v.enhance.gameObject:SetActive(true)
    end
end

--给扑克蜡封
function P:SealPoker(pokerList, type)
    for _,v in pairs(pokerList) do
        v.data.seals = type
        -- v.seal.sprite = 
        v.seal.gameObject:SetActive(true)
    end
end

--转变扑克花色
function P:ChangePokerSuit(pokerList, type)
    for _,v in pairs(pokerList) do
        v.data.suit = type
        -- v.icon.sprite = 
        -- BlindManager:CheckPokerWeaken(v)
    end
end

--提高扑克点数
function P:UpPokerPoint(pokerList, val)
    for _,v in pairs(pokerList) do
        local upValue = v.data.point + val
        local maxPokerNum = table.nums(Bal.PokerValue)
        if upValue > maxPokerNum then
            upValue = upValue - maxPokerNum
        end
        v.data.point = upValue
        --todo
        -- local pokerConfigId = self:GetPokerConfigId(v.data.suit, upValue)
        -- v.data.value = CardDevelopModel:GetPokerChip(pokerConfigId)
        -- v.icon.sprite = self:GetPokerIcon(v.data)
        -- BlindManager:CheckPokerWeaken(v)
    end
end

--获得扑克牌价格
function P:GetPokerPrice(cardData)
    local editionCost = tpl_[cardData.edition].cost
    
    local enhanceConfig = tpl_[cardData.enhance]
    local enhanceCost = enhanceConfig and enhanceConfig.cost or 0

    local sealConfig = tpl_[cardData.seals]
    local sealCost = sealConfig and sealConfig.cost or 0

    local cost = 1 + editionCost + enhanceCost + sealCost
    return cost
end

--购买扑克牌
function P:BuyPoker(card, cost)
    if not BalBattleModel:checkCurrencySufficient(cost) then
        -- bee.emit("")
        return
    end

    self:AddNewPoker(card.data, true)
    -- bee.emit("")

    BalBattleModel:changeCurrency(-cost)
    BaseCardUtil:recoveryCard(card)
end

--获取手中扑克
function P:GetDisplayPokerByUid(uid)
    -- local list = ConsumeManager.ctrlingPackage and ConsumeManager.packagePokerList or BattleManager.displayPokerList
    -- for _,v in pairs(list) do
    --     if v.uid == uid then
    --         return v
    --     end
    -- end
    -- return nil
end


--回收扑克
function P:recoveryCard(card)
    
end

return P