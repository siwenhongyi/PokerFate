local P = class("HalloweenCardJoker", Object)
HalloweenCardJoker = P

function P:ctor()

end

function P:onAwake()
    self.data = nil
    self.index = 0
    self.longPress = false
    self.draging = false
    self.selecting = false
    self.tweening = false

    self.AnimRoot = self:find("AnimRoot").transform
    self.ani = self.AnimRoot:GetComponent("Animator")
    self.Center = self:find("Center", self.AnimRoot)

    self.quailtyStr = {[1] = "green", [2] = "blue", [3] = "purple", [4] = "orange"}
    self.CardBack = self:find("Card/card_joker_rarity_bg", self.Center)
    self.CardFrame = self:find("Card/card_joker_rarity", self.Center)
    self.CardIcon = self:find("Card/character/icon", self.Center)
    self.CardCamp = self:find("Card/Camp", self.Center)
    self.tagStr = {[1] = "star", [2] = "flower", [3] = "heart"}
    self.FactionIcon = self:find("Faction/Icon", self.Center)
    self.Fx = self:find("Eff_poker_Joker_sx", self.Center)

    self.RefreshBtn = self:find("Refresh", self.Center)
    bee.addClick(self.RefreshBtn, function ()
        if GuideManager:isInGuide() then
            return
        end
        Game:playSound("ui_button_confirm")
        self:refreshCardEvent(self.index)
        -- BalBattleModel:refreshJokerCard(self.index)
    end)

    self.btn = self.node:GetComponent("EventTriggerListener")
    self:buttonDownEx()
end

--牌背
-- function P:setCardBack()
--     local cardBackImage = DecorationModel:getCurCardBackImage(BalBattleModel:getScheme())
--     bee.setIcon(self.Back, cardBackImage)
-- end

--角色
function P:setData(data)
    self.data = data
    local cfg = tpl_fate_character[self.data.skillId]
    bee.setIcon(self.CardBack, string.format("Card[card_joker_rarity_%s_bg]", self.quailtyStr[cfg.quality]))
    bee.setIcon(self.CardFrame, string.format("Card[card_joker_rarity_%s]", self.quailtyStr[cfg.quality]))

    self.FactionIcon:SetActive(cfg.tag ~= nil)
    if cfg.tag then
        bee.setIcon(self.FactionIcon, string.format("Card[card_joker_faction_%s_%s]", self.quailtyStr[cfg.quality], self.tagStr[cfg.tag]))
    end

    local roleSkinCfg = tpl_character_skin[cfg.skin_id]
    local roleCfg = tpl_character[roleSkinCfg.role]
    local campNum = self.CardCamp.transform.childCount
    for i = 1, campNum do
        local campTran = self.CardCamp.transform:GetChild(i - 1)
        local checkCamp = campTran.name == string.format( "card_joker_camp_%d", roleCfg.campInt)
        bee.setIcon(campTran, string.format("Card[card_joker_%s_camp_%d]", self.quailtyStr[cfg.quality], roleCfg.campInt))
        campTran.gameObject:SetActive(checkCamp)
    end

    bee.setIcon(self.CardIcon, roleSkinCfg.image, true)
    self.CardIcon.transform.localPosition = bee.v3(roleSkinCfg.leaderboard_offset[1], roleSkinCfg.leaderboard_offset[2], 0)
    self.CardIcon.transform.localScale = bee.v3(roleSkinCfg.leaderboard_offset[3], roleSkinCfg.leaderboard_offset[3], 1)

    if roleSkinCfg.spine_rotation then
        self.CardIcon.transform.localEulerAngles = bee.v3(0, 0, roleSkinCfg.spine_rotation)
    else
        self.CardIcon.transform.localEulerAngles = bee.v3zero
    end
end

function P:setUnlockData()
    self.data = JokerUtil:creatNewJokerData()
    bee.setIcon(self.CardBack, string.format("Card[card_joker_rarity_%s_bg]", self.quailtyStr[1]))
    bee.setIcon(self.CardFrame, string.format("Card[card_joker_rarity_%s]", self.quailtyStr[1]))
    bee.setGray(self.CardBack, true)
    bee.setGray(self.CardFrame, true)
    self.CardIcon:SetActive(false)
    self.FactionIcon:SetActive(false)
    self.CardCamp:SetActive(false)
end

--设置刷新
function P:setRefresh(isShow)
    self.RefreshBtn:SetActive(isShow)
end

--按钮事件拓展
function P:buttonDownEx()
    self.btn.onDown:AddListener(function (_, eventData)
        if self._buttonExReleaseTag then
            scheduler:removeTag(self._buttonExReleaseTag)
        end

        local pointerId = eventData.pointerId
        self._buttonExReleaseTag = bee.loopTimer(0, 0.01, function ()
            local isPointerHeld = false
            if pointerId >= 0 then
                for i = 0, CU.Input.touchCount - 1 do
                    local touch = CU.Input.GetTouch(i)
                    if touch.fingerId == pointerId then
                        isPointerHeld = touch.phase ~= CU.TouchPhase.Ended
                            and touch.phase ~= CU.TouchPhase.Canceled
                        break
                    end
                end
            else
                local mouseButton = pointerId == -2 and 1 or pointerId == -3 and 2 or 0
                isPointerHeld = CU.Input.GetMouseButton(mouseButton)
            end

            if isPointerHeld then
                return
            end

            local releaseTag = self._buttonExReleaseTag
            self._buttonExReleaseTag = nil
            scheduler:removeTag(releaseTag)

            if self.longPress and not self.draging then
                self.btn.onUp:Invoke(self.node, eventData)
            end
        end, self.node)
    end)
end

--刷新
function P:refreshCardEvent(index)
    if BalBattleModel.jokerRefreshRemain > 0 then
        UiManager:showUI("HalloweenHint", {
            text = _T("TAB_JOKER_DEC_1"),
            tip = _F("TAB_JOKER_DEC_21", BalBattleModel.jokerRefreshRemain, tpl_constdata.Refresh_Count),
            onSure = function()
                BalBattleModel:refreshJokerCard(index)
            end,
        })
        -- UiManager:showTip({
        --     text = _T("TAB_JOKER_DEC_1"),
        --     subText = _F("TAB_JOKER_DEC_21", BalBattleModel.jokerRefreshRemain, tpl_constdata.Refresh_Count),
        --     onSure = function()
        --         BalBattleModel:refreshJokerCard(index)
        --     end,
        -- })
        return
    end

    local refreshCost = tpl_constdata.Refresh_Cost
    local itemId = refreshCost[1]
    local itemCount = refreshCost[2]
    if ItemModel:getItemNumById(itemId) < itemCount then
        UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
        UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(itemId, true)})
        return
    end

    local itemName = _T(tpl_props[itemId].name)

    local costText = _F("<icon name=Icon[icon_activity_s10_01] w=80 h=80/> x {p2}", itemName, itemCount)
    UiManager:showUI("HalloweenHint", {
        richText = _F("TAB_JOKER_DEC_22", costText),
        onSure = function()
            BalBattleModel:refreshJokerCard(index)
        end,
    })
    -- UiManager:showTip({
    --     richText = _F("TAB_JOKER_DEC_22", costText),
    --     onSure = function()
    --         BalBattleModel:refreshJokerCard(index)
    --     end,
    -- })
end

function P:refreshJokerCallback(jokerData)
    self.Fx:SetActive(true)
    self:once(0.35, function ()
        self:setData(jokerData)
    end)
    self:once(1.8, function ()
        self.Fx:SetActive(false)
    end)
end

return P