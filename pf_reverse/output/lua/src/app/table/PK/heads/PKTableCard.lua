local P = class("PKTableCard", Object)

-- 玩家显示在牌桌上的牌及 button
function P:ctor(params)
    self.seatid = 1

	self._index = params and params.index or 1
end

function P:setIndex(i)
    self._index = i
    self.seatid = i
end

function P:setSeatId(i)
    self.seatid = i
end

function P:onAwake()
    self.ImageButton = self:find("ImageButton")
    self.BgCard = self:find("BgCard")

    self:setButtonVisible(false)
end

function P:initTableCards()
    if not self.Ani_card then
        if self.data:isOmaha() then
            self.Ani_card = bee.createObj("views/table/PK/Ani_card_omaha" .. self._index)
        else
            self.Ani_card = bee.createObj("views/table/PK/Ani_card" .. self._index)
        end
        -- self.Ani_card = bee.createObj("views/table/PK/Ani_card" .. self._index)
        self.Ani_card.transform:SetParent(self.BgCard.transform, false)
        self.ImageCards = {
            self:find("ImageCard1", self.Ani_card),
            self:find("ImageCard2", self.Ani_card),
            self:find("ImageCard3", self.Ani_card),
            self:find("ImageCard4", self.Ani_card),
        }
        for _, v in ipairs(self.ImageCards) do
            bee.setSpriteImg(v, PlayerModel:getCurCardBackImage())
        end
    end
end

function P:refreshUI()
    self.data, self.tableLayer = GameModel.data, GameModel.layer
    self:initTableCards()
    self:setButtonVisible(false)
    self:playCardAnim("Ui_poker_fold_idle")
    -- self:showCard(false)
    self:refreshCard()
end

function P:setButtonVisible(isShow)
    self.ImageButton:SetActive(false)
    -- self.ImageButton:SetActive(isShow)
end

function P:refreshIdle()
    self:playCardAnim("Ui_poker_fold_idle")
end

function P:refreshCard()
	local info = self.data:getPlayer(self.seatid)
	if not self.data:isPlaying() or not info or not info.has_card or info.is_fold or self:isMe() then
		for _, v in ipairs(self.ImageCards) do
			v:SetActive(false)
		end
		return
	end

	for i, v in ipairs(self.ImageCards) do
        v:SetActive(true)
		if info.hand_cards and info.hand_cards[i] then
			bee.setIcon(v, GF.getCardImageByCode(info.hand_cards[i]))
		else
			bee.setIcon(v, GF.getCardImageByCode(0))
		end
	end
    self:playCardAnim("Ui_poker_fold_idle")

	local c = info.is_fold and COLOR.main_grey or COLOR.main_white
	for _, v in ipairs(self.ImageCards) do
		bee.setColor(v, c, "SpriteRenderer")
	end
end

function P:showCard(isShow, index)
    if index then
        self.ImageCards[index]:SetActive(isShow)
    else
        for _, v in ipairs(self.ImageCards) do
            v:SetActive(isShow)
        end
    end

    local info = self.data:getPlayer(self.seatid)
    if isShow then
        for k, v in ipairs(self.ImageCards) do
            if not index or k == index then
                bee.setSprite(v, GF.getCardImageByCode(info.hand_cards and info.hand_cards[k] or 0))
                bee.setColor(v, COLOR.main_white, "SpriteRenderer")
            end
        end
    end
end

function P:showCardType(cardType, cards)
    -- 高亮赢牌特效
    if cards then
        local info = self.data:getPlayer(self.seatid)
        for _, v in ipairs(cards) do
            for k, code in ipairs(info.hand_cards) do
                if code == v then
                    bee.setColor(self.ImageCards[k], COLOR.main_white, "SpriteRenderer")
                end
            end
        end
    end
end

function P:foldCard()
    if self.data:getHandCardNum() == 2 then
        self:playCardAnim("Ui_poker_fold_" .. self._index)
    else
        self:playCardAnim("Ui_poker_fold_omaha_" .. self._index)
    end
end

function P:setCardGrep()
	for _, v in ipairs(self.ImageCards) do
		bee.setColor(v, COLOR.main_grey, "SpriteRenderer")
	end
end

function P:playCardAnim(name)
	local anim = self.Ani_card:GetComponent("Animator")
    anim:Play(name, -1, 0)
end

function P:getCardPosiiton(index)
    return self.ImageCards[index].transform.position
end

-- 牌局结束后，回收止牌
function P:recyclingCards()
    local player = self.data:getPlayer(self.seatid)
    if player.is_fold or GF.isFoldAction(player.action_type) then
        self:playCardAnim("Ui_poker_fold_idle")
        for _, v in ipairs(self.ImageCards) do
            v:SetActive(false)
        end
        return
    end
    for _, v in ipairs(self.ImageCards) do
        if v.activeSelf then
            v:SetActive(false)
            local card = self.tableLayer:getTableImageCard()
            card.transform.localScale = v.transform.localScale
            card.transform.localEulerAngles = v.transform.localEulerAngles
            card.transform.position = v.transform.position
            self.tableLayer._nodeCache:addUsing(card)
            bee.tween(card, true)
            : to(0.45, {position = self.tableLayer.dealCardWorldPos, rotate = bee.v3zero, scale = bee.v3(0.3, 0.3, 0.3)}, {rotate = DT.RotateMode.FastBeyond360})
            : onComplete(function()
                self.tableLayer:_putDealTmpCard(card)
            end)
            : link()
        end
    end
end

function P:isMe()
	local info = self.data:getPlayer(self.seatid)
	return info and info.uid == PlayerModel:getUid()
end

