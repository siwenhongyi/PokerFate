local P = {
    jokerPosDic = {}
}
JokerUtil = P

--鬼牌基础数据
function P:creatNewJokerData()
    local cardData = {
        --uid
        uid = 0,
        --卡类
        category = Bal.CardCategory.Joker,
        --所在位置
        -- place = B.CardPlaceType.None,
        --技能id
        skillId = 0,
        --版本
        edition = 0,
        --失效
        invalid = false,
        --增值价格
        addedPrice = 0,
        --技能参数
        skillParams = {
            accCount = 0, --累积数量
            randomSuit = 0, --随机花色
            randomCardType = nil, --随机牌型
            floatChip = 0, --浮动筹码
            floatPower = 0, --浮动倍率
            floatMulPower = 0, --浮动倍乘
        },
    }
    return cardData
end

--创建鬼牌
function P:CreateJokerCardItem(skillId, edition)
    local data = self:CreateJokerCardData(skillId, edition)
    local card = self:CreateJokerCardItemByData(data)
    return card
end
--创建鬼牌数据
function P:CreateJokerCardData(skillId, edition)
    local data = self:creatNewJokerData()
    data.uid = BalBattleModel:getNewUid()
    data.skillId = skillId
    -- data.edition = edition or BBM:GetRandomEdition(true)
    -- data.edition = bee.GetRandom(100, 104) + 1
    return data
end
function P:CreateJokerCardItemByData(data)
    local card = bee.createObj("views/Balatro/BalatroBaseCard")
    local cls = ObjectPool:getCls(card)
    cls:setData(data)
    -- card.idleSpeed = bee.GetRandomFloat(1, 3)
    -- BattleShownUtil:CardIdleAni(card)
    -- BaseCardUtil:SetCardStrengthen(card, data)
    return card
end

--随机获取一张鬼牌卡
function P:GetRandomJokerCard(quality, edition)
    local configId = self:getRandomJokerConfigId(quality)
    local joker = self:CreateJokerCardItem(configId, edition)
    return joker
end
--随机获取鬼牌配置id
function P:getRandomJokerConfigId(quality)
    return 0
end

--随机获取一张卡包鬼牌
function P:GetRandomJokerCardInPackage(probabilityData)
    local configId = self:getRandomJokerConfigIdInPackage(probabilityData)
    local joker = self:CreateJokerCardItem(configId)
    return joker
end
--随机获取一张卡包内的鬼牌配置id
function P:getRandomJokerConfigIdInPackage(probabilityData)
    return 0
end


--点击卡槽内的鬼牌
function P:ClickJokerInSlot(card, click)
    BaseCardUtil:SwitchCardSelecting(card, click)

    -- if card.selecting then
    --     bee.emit(BattleSignal.SelectingBattleSoltCardSignal, {type = B.BattleSoltType.Joker})
    --     for _,v in pairs(BattleManager.jokerCardList) do
    --         if v.uid ~= card.uid and v.selecting then
    --             self:ClickJokerInSlot(v)
    --         end
    --     end
    --     card.tran:SetAsLastSibling()
    --     card.functionTran.gameObject:SetActive(BattleManager.mainlineId ~= BattleManager.openingMainId)
    --     local cost = self:GetJokerSellPrice(card.data)
    --     local baseStr = TranslateManager:GetTranslate(TranslateId.BattleSell)
    --     card.functionText.text = string.format('%s $%d', baseStr, cost)
    --     card.functionBtn.onClick = function() self:SellJokerCard(card.data, cost) end
    -- else
    --     card.functionTran.gameObject:SetActive(false)
    --     card.tran:SetSiblingIndex(card.index - 1)
    -- end
end

--点击商店内的鬼牌
function P:ClickJokerInShop(card, click)
    BaseCardUtil:SwitchCardSelecting(card, click)

    -- if card.selecting then
    --     bee.emit(BattleSignal.SelectingBattleShopCardSignal, {type = ShopSoltType.Card})
    --     bee.emit(BattleSignal.SelectShopCardSignal, {uid = card.uid})

    --     card.tran:SetAsLastSibling()
    --     card.confirmTran.gameObject:SetActive(true)
    -- else
    --     card.confirmTran.gameObject:SetActive(false)
    -- end
end

--点击补充包内的鬼牌
function P:ClickJokerInSupplement(card, click)
    BaseCardUtil:SwitchCardSelecting(card, click)

    -- if card.selecting then
    --     bee.emit(BattleSignal.SelectPackageCardSignal, {uid = card.uid})
    --     card.confirmTran.gameObject:SetActive(true)
    -- else
    --     card.confirmTran.gameObject:SetActive(false)
    -- end
end

--购买鬼牌
function P:buyJoker(card, cost)
    local enough = BalBattleModel:checkCurrencySufficient(cost)
    if not enough then
        return
    end

    local geted = self:getJoker(card)
    if geted then
        -- bee.emit("")
        BalBattleModel:changeCurrency(-cost)
    end
end

--获得鬼牌
function P:getJoker(card)
    --数量上限
    if BalBattleModel:checkJokerMax() then
        bee.emit("")
        return false
    end

    BalBattleModel:getJoker(card)
    BalSkillUtil:getJoker(card)
    return true
end

--出售鬼牌
function P:sellJoker(card, cost)
    BalBattleModel:sellJoker(card)
    BalSkillUtil:sellJoker(card)

    BalBattleModel:changeCurrency(cost)
end

--排序鬼牌
function P:sortDisplayCardPos()
    
end

--获取鬼牌基础价格
function P:getJokerPrice(jokerData)
    local config = tpl_fate_character[jokerData.skillId]
    return BalSkillUtil:getDiscount(config.cost)
end

--获取鬼牌售价
function P:getJokerSellPrice(jokerData)
    local cost = self:getJokerPrice(jokerData)
    local cost = math.max(1, math.floor(cost * 0.5)) + jokerData.addedPrice
    return cost
end

--获取当前全部鬼牌的售价
function P:getAllJokerSellPrice()
    local totalCost = 0
    for _,v in pairs(BalBattleModel.ownedJokerList) do
        totalCost = totalCost + self:getJokerSellPrice(v)
    end
    return totalCost
end

--鬼牌描述
function P:showJokerDetail(jokerCls, infoMask)
    local infoTran = bee.find("Info", infoMask)
    if infoTran == nil then
        return
    end

    infoMask:SetActive(true)
    local cfg = tpl_fate_character[jokerCls.data.skillId]
    local nameMask = bee.find("NameMask", infoTran)
    local nameText = bee.find("NameMask/Name", infoTran)
    bee.setText(nameText, _T(cfg.cardname))
    local dec = ""
    if cfg.mark then
        dec = BalSkillUtil:getJokerDecMark(cfg, jokerCls.data)
    else
        dec = _T(cfg.dec)
    end
    bee.setText(bee.find("Text", infoTran), dec)

    infoTran.transform.position = jokerCls.transform.position
    infoTran.transform.localPosition = infoTran.transform.localPosition + bee.v3(0, -170, 0)

    if nameMask and nameText then
        local s = nameMask.transform.sizeDelta
        local len = nameText:GetComponent("Text").preferredWidth
        bee.Tween.killByTarget(nameText)
        if len <= s.x then
            nameText.transform.localPosition = bee.v3zero
        else
            local offset = (len - s.x) / 2 + 10
            nameText.transform.localPosition = bee.v3(offset)
            bee.tween(nameText)
            : to(5, {position = bee.v3(-offset, 0, 0)})
            : delay(3)
            : to(0, {position = bee.v3(offset, 0, 0)})
            : loop(-1)
            : link()
            : setTarget()
        end
    end
end

return P