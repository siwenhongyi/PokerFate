local P = class("PKPlayerCard", Object)

-- 玩家的手牌

function P:setData(data, seatid, head)
    self.data = data
    self.seatid = seatid
    self.head = head
end

function P:playSound(key)
	local info = self.data:getPlayer(self.seatid)
	if info then
		local d = tpl_character_skin[info.skin_id]
		if d then
			Game:playRoleInVoice(d.role, key)
		end
	end
end

function P:onAwake()
    self.ImageCards = {
        self:find("ImageCard1"),
        self:find("ImageCard2"),
        self:find("ImageCard3"),
        self:find("ImageCard4"),
    }

    self.Eff_poker_card_sg = {}
    for k, v in ipairs(self.ImageCards) do
        self.Eff_poker_card_sg[k] = self:find("Eff_poker_card_sg", v)
    end
    
    -- 胜利显示节点
    self.ResultWins = {
        self:find("BgWin", self.ImageCards[1]),
        self:find("BgWin", self.ImageCards[2]),
        self:find("BgWin", self.ImageCards[3]),
        self:find("BgWin", self.ImageCards[4]),
    }
    self.ImageWin = self:find("ImageWin")
    -- 失败显示节点
    self.ResultLoses = {
        self:find("BgLose", self.ImageCards[1]),
        self:find("BgLose", self.ImageCards[2]),
        self:find("BgLose", self.ImageCards[3]),
        self:find("BgLose", self.ImageCards[4]),
    }
    -- 失败显示节点
    self.BgLights = {
        self:find("BgLight", self.ImageCards[1]),
        self:find("BgLight", self.ImageCards[2]),
        self:find("BgLight", self.ImageCards[3]),
        self:find("BgLight", self.ImageCards[4]),
    }
	-- 秀牌眼睛
	self.BgEyes = {
        self:find("EyeTag", self.ImageCards[1]),
        self:find("EyeTag", self.ImageCards[2]),
        self:find("EyeTag", self.ImageCards[3]),
        self:find("EyeTag", self.ImageCards[4]),
	}

    self.ImageLose = self:find("ImageLose")
    self.BgHandType = self:find("BgHandType")
    self.BgHandType2 = self:find("BgHandType2")
    self.TextHandType = self:find("BgHandType/TextHandType")
    self.BgCardValue = self:find("BgCardValue", self.BgHandType)
	if self.BgHandType2 then
    	self.TextHandType2 = self:find("BgHandType2/TextHandType")
	end

	for _, v in ipairs(self.BgLights) do
		v:SetActive(false)
	end

	if #self.BgEyes > 0 then
		for k, v in ipairs(self.ImageCards) do
			bee.addClick2(v, function()
				if not SettingModel:isShowCard() then
					return
				end
				if not self.data or not bee.checkCd("PKPlayerCard_showEyeTag_" .. k, 0.5) then return end
				local info = self.data:getPlayer(self.seatid)
				if info and info:isMe() and self.data:isPlaying() and info.has_card then
					Net:sendReq("pb.ShowMyCardREQ", {
						gameid = self.data:getGameId(),
						pos = k,
						flag = self.BgEyes[k].activeSelf and 0 or 1,
					})
				end
			end)
		end
	end
end

function P:refreshEyes()
	if #self.BgEyes > 0 and self.node.activeSelf then
		local info = self.data:getPlayer(self.seatid)
		if not info or not info:isMe() then
			return
		end

		local show_card_info = self.data:getShowCardInfo()
		for i, v in ipairs(self.ImageCards) do
			if info.hand_cards and info.hand_cards[i] then
				if self.BgEyes[i] then
					if show_card_info and info:isMe()  then
						self.BgEyes[i]:SetActive(show_card_info[i] == 1)
					else
						self.BgEyes[i]:SetActive(false)
					end
				end
			else
				if self.BgEyes[i] then
					self.BgEyes[i]:SetActive(false)
				end
			end
		end
	end
end

function P:refreshCard(is_reset)
	if not bee.isNull(self._cardNode) then
		GameModel.layer:putEffectItem(self._cardNode)
		self._cardNode = null
	end
	self.BgHandType:SetActive(false)
	if self.BgHandType2 then
		self.BgHandType2:SetActive(false)
	end
	if self.BgCardValue then
		self.BgCardValue:SetActive(false)
	end
	if is_reset then
		for _, v in ipairs(self.BgLights) do
			v:SetActive(false)
		end
	end
	local info = self.data:getPlayer(self.seatid)
	if not self.data:isPlaying() or not info or not info.has_card or not info.hand_cards or info.hand_cards[1] == 0 then
		for _, v in ipairs(self.ImageCards) do
			v:SetActive(false)
			local eft = self:find("Eff_poker_card_sg", v)
			if eft then
				eft:SetActive(false)
			end
		end
		self.node:SetActive(false)
		return
	end
	self.node:SetActive(true)

	local show_card_info = nil
	if info:isMe() then
		show_card_info = self.data:getShowCardInfo()
	end
	for i, v in ipairs(self.ImageCards) do
		v.transform.localScale = bee.v3one
		if info.hand_cards and info.hand_cards[i] then
			bee.setIcon(v, GF.getCardImageByCode(info.hand_cards[i]))

			if self.BgEyes[i] then
				if show_card_info and info:isMe()  then
					self.BgEyes[i]:SetActive(show_card_info[i] == 1)
				else
					self.BgEyes[i]:SetActive(false)
				end
			end
		else
			bee.setIcon(v, GF.getCardImageByCode(0))

			if self.BgEyes[i] then
				self.BgEyes[i]:SetActive(false)
			end
		end
	end

	local c = info.is_fold and COLOR.main_grey or COLOR.main_white
	local scale = info.is_fold and 0.8 or 1
	for _, v in ipairs(self.ImageCards) do
		bee.setColor(v, c)
		v.transform.localScale = bee.v3(scale, scale, scale)
	end
	if info.is_fold then
		-- self:showLoseNodes(true)
	end
end

function P:showCard(visible, index, isBack)
	if index then
		self.ImageCards[index]:SetActive(visible)
	else
		for _, v in ipairs(self.ImageCards) do
			v:SetActive(visible)
		end
	end
	
	if visible then
		self.node:SetActive(true)
		local info = self.data:getPlayer(self.seatid)
		for i, v in ipairs(self.ImageCards) do
			if not index or i == index then
				bee.Tween.killByTarget(v)
				v:SetActive(true)
				local code = info.hand_cards and info.hand_cards[i] or 0
				if isBack then
					code = 0
				end
				bee.setIcon(v, GF.getCardImageByCode(code))
				bee.setColor(v, COLOR.main_white)
				v.transform.localScale = bee.v3one
			end
		end
	end
end

-- 强制显示，尝试修正看不到牌问题
function P:showCardForce()
	local info = self.data:getPlayer(self.seatid)
	if info:isMe() then 	
		self.node:SetActive(true)
		for i, v in ipairs(self.ImageCards) do
			v:SetActive(true)
			local code = info.hand_cards and info.hand_cards[i] or 0
			bee.setIcon(v, GF.getCardImageByCode(code))
		end
	end
end

function P:flopCard(node, code, cb)
	bee.tween(node)
	: to(0.1, {scale = bee.v3(0, 1, 1)})
	: call(function()
		bee.setIcon(node, GF.getCardImageByCode(code))
	end)
	: to(0.1, {scale = bee.v3(1, 1, 1)})
	: call(function()
		if cb then cb() end
	end)
	: setTarget()
	: link()
end

function P:showCardAndFlop(isDealing)
	self:showCard(true, nil, isBack)
	local info = self.data:getPlayer(self.seatid)
	local isCb = false
	for i, v in ipairs(self.ImageCards) do
		local code = info.hand_cards and info.hand_cards[i] or 0
		if code > 0 then
			self:flopCard(v, code, function()
				if not isCb then
					isCb = true
					Game:playSound("ui_card_turn")
					self._isDealing = isDealing
					if isDealing then
						GameModel.layer:refreshCardType()
					end
					self._isDealing = nil
				end
			end)
		end
	end
end

function P:showCardStatus()
	self._cardNode = GameModel.layer:playUIEffect("views/table/PK/CardStatus", self.node.transform, nil, -1)
end

function P:showCardType(cardType, cards, isDealing, pkType)
	self:refreshWinRate()
		
	if nil == cardType or "" == cardType then
		self.BgHandType:SetActive(false)
		if self.BgHandType2 then
			self.BgHandType2:SetActive(false)
		end
		if self.BgCardValue then
			self.BgCardValue:SetActive(false)
		end
		for _, v in ipairs(self.BgLights) do
			v:SetActive(false)
		end
        return
	end

    local info = self.data:getPlayer(self.seatid)
    if info.is_fold then
        self.BgHandType:SetActive(false)
		if self.BgHandType2 then
			self.BgHandType2:SetActive(false)
		end
        if self.BgCardValue then
            self.BgCardValue:SetActive(false)
        end
		for _, v in ipairs(self.BgLights) do
			v:SetActive(false)
		end
        return
    end
    local boards = self.data:getBoardInfo()
    if self.BgCardValue then
        if not SettingModel:isCardValue() then
            self.BgCardValue:SetActive(false)
			if self._isDealing then
				if info.hand_cards and GF.getCardNumber(info.hand_cards[1]) == GF.getCardNumber(info.hand_cards[2]) then
					self:playSound(ROLE_VOICE.one_pair)
				else
					self:playSound(ROLE_VOICE.high_card)
				end
			end
		elseif boards and #boards > 0 then
			self.BgCardValue:SetActive(false)
        else
            self.BgCardValue:SetActive(true)
            local handValue = info:getHandsValue()
            if 1 == handValue then
                self:find("ImageBar1", self.BgCardValue):SetActive(true)
                self:find("ImageBar2", self.BgCardValue):SetActive(false)
                if self._isDealing then
                    self:playSound(ROLE_VOICE.strong_cards)
                end
            elseif 2 == handValue then
                self:find("ImageBar1", self.BgCardValue):SetActive(false)
                self:find("ImageBar2", self.BgCardValue):SetActive(true)
                if self._isDealing then
                    self:playSound(ROLE_VOICE.weak_cards)
                end
            else
                self:find("ImageBar1", self.BgCardValue):SetActive(false)
                self:find("ImageBar2", self.BgCardValue):SetActive(true)
                if self._isDealing then
					if info.hand_cards and GF.getCardNumber(info.hand_cards[1]) == GF.getCardNumber(info.hand_cards[2]) then
						self:playSound(ROLE_VOICE.one_pair)
					else
						self:playSound(ROLE_VOICE.high_card)
					end
                end
            end
        end
    end
	if self.BgHandType2 and self.BgCardValue and not self.BgCardValue.activeSelf then
    	self.BgHandType:SetActive(false)
		self.BgHandType2:SetActive(true)
	else
    	self.BgHandType:SetActive(true)
	end
    bee.setText(self.TextHandType, _T(cardType))
	if self.TextHandType2 then
		bee.setText(self.TextHandType2, _T(cardType))
	end
    
    if not self._isDealing and info:isMe() and isDealing and (boards and #boards > 0) then
		local soundFlag = true
		if #boards == 3 then
			self._lastCardType = cardType
		elseif self._lastCardType == cardType then
			soundFlag = false
		else
			self._lastCardType = cardType
		end
		if soundFlag then
			if cardType == "LAB_HIGH_CARD" then
				self:playSound(ROLE_VOICE.high_card)
			elseif cardType == "LAB_ONE_PAIR" then
				self:playSound(ROLE_VOICE.one_pair)
			elseif cardType == "LAB_TWO_PAIRS" then
				self:playSound(ROLE_VOICE.two_pairs)
			elseif cardType == "LAB_THREE_KIND" then
				self:playSound(ROLE_VOICE.three_of_a_kind)
			elseif cardType == "LAB_STRAIGHT" then
				self:playSound(ROLE_VOICE.straight)
			elseif cardType == "LAB_FLUSH" then
				self:playSound(ROLE_VOICE.flush)
			elseif cardType == "LAB_FULL_HOUSE" then
				self:playSound(ROLE_VOICE.full_house)
			elseif cardType == "LAB_QUADS" then
				self:playSound(ROLE_VOICE.four_of_a_kind)
			elseif cardType == "LAB_STRAIGHT_FLUSH" then
				self:playSound(ROLE_VOICE.straight_flush)
			elseif cardType == "LAB_ROYAL_FLUSH" then
				self:playSound(ROLE_VOICE.royal_flush)
			end
		end
    end

    local lightIdxes = {}
    if cards and boards and #boards > 0 then
        for k, code in ipairs(info.hand_cards) do
            for _, v in ipairs(cards) do
                if code == GF.getCardCode(v) then
                    if self.data:getHandCardNum() > 2 or (pkType and pkType >= tpl_constdata.IngameTipType) then
                        lightIdxes[k] = true
                        break
                    end
                end
            end
        end
    end
    if next(lightIdxes) then
        for k, v in ipairs(self.ImageCards) do
            if lightIdxes[k] then
				if info:isMe() and pkType and pkType >= tpl_constdata.IngameTipType then
                	self.BgLights[k]:SetActive(true)
				else
					self.BgLights[k]:SetActive(false)
				end
                bee.setColor(v, COLOR.main_white)
                if self.Eff_poker_card_sg[k] and not self.Eff_poker_card_sg[k].activeSelf then
                    self.Eff_poker_card_sg[k]:SetActive(true)
                end
            else
                self.BgLights[k]:SetActive(false)
                if self.Eff_poker_card_sg[k] then
                    bee.setColor(v, COLOR.main_grey)
                    self.Eff_poker_card_sg[k]:SetActive(false)
                end
            end
        end
    else
        for k, v in ipairs(self.ImageCards) do
            self.BgLights[k]:SetActive(false)
            bee.setColor(v, COLOR.main_white)
            if self.Eff_poker_card_sg[k] then
                self.Eff_poker_card_sg[k]:SetActive(false)
            end
        end
    end

	if info:isMe() then
		self:showCardForce()
	end
end

function P:setCardGrep()
	for _, v in ipairs(self.ImageCards) do
		bee.setColor(v, COLOR.main_grey)
		v.transform.localScale = Config.CARD_SCALE_LOSE
	end
end

function P:showWinNodes(flag)
	if flag and 4 == #self.ResultWins then
		self:showOmahaWinHands()
	else
		for _, v in ipairs(self.ResultWins) do
			v:SetActive(flag)
		end
	end
	self.ImageWin:SetActive(flag)
    if flag then
        local anim = "Prefab/PKTable/Eff_poker_logo_win"
		local winType = self.data:getWinType(self.seatid)
		if 1 == winType then
			anim = "Prefab/PKTable/Eff_poker_logo_bigwin"
		elseif 2 == winType then
			anim = "Prefab/PKTable/Eff_poker_logo_magewin"
		end
		self._WinAnim = GameModel.layer:playUIEffect(anim, self.node.transform, self.ImageWin.transform.localPosition, 4)
    	local info = self.data:getPlayer(self.seatid)
		if info:isMe() then
			self._WinAnim.transform.localScale = bee.v3one
		else
			self._WinAnim.transform.localScale = bee.v3(1.6, 1.6, 1.6)
		end
		if not bee.isNull(self._PKWinRate) then
			GameModel.layer:putEffectItem(self._PKWinRate)
			self._PKWinRate = nil
		end
	elseif not bee.isNull(self._WinAnim) then
		GameModel.layer:putEffectItem(self._WinAnim)
		self._WinAnim = nil
    end
end

function P:showLoseNodes(flag)
	if flag and 4 == #self.ResultLoses then
		self:showOmahaWinHands()
	else
		for _, v in ipairs(self.ResultLoses) do
			v:SetActive(flag)
		end
	end
	self.ImageLose:SetActive(flag)
	if flag then
		self._LoseAnim = GameModel.layer:playUIEffect("Prefab/PKTable/Eff_poker_logo_lose", self.node.transform, self.ImageLose.transform.localPosition, 4)
		local info = self.data:getPlayer(self.seatid)
		if info:isMe() then
			self._LoseAnim.transform.localScale = bee.v3one
		else
			self._LoseAnim.transform.localScale = bee.v3(1.6, 1.6, 1.6)
		end
		if not bee.isNull(self._PKWinRate) then
			GameModel.layer:putEffectItem(self._PKWinRate)
			self._PKWinRate = nil
		end
	elseif not bee.isNull(self._LoseAnim) then
		GameModel.layer:putEffectItem(self._LoseAnim)
		self._LoseAnim = nil
	end
end

function P:showOmahaWinHands()
	local boards = self.data:getBoardInfo()
	local player = self.data:getPlayer(self.seatid)
	if player.hand_cards then
		local cards, cardType = PKHelper.getCardType(player.hand_cards, boards, self.data:getRoomType())
		for k, v in ipairs(player.hand_cards) do
			local flag = false
			for _, c in ipairs(cards) do
				if v == GF.getCardCode(c.number, c.color) then
					flag = true
					break
				end
			end
			if flag then
				self.ResultWins[k]:SetActive(true)
				self.ImageCards[k].transform.localScale = bee.v3one
			else
				self.ResultLoses[k]:SetActive(true)
				self.ImageCards[k].transform.localScale = Config.CARD_SCALE_LOSE
			end
		end
	end
end

function P:refreshWinRate()
    local info = self.data:getPlayer(self.seatid)
	if not self.data:isAllAllin() or not info or info.is_fold or not self.data:isCanShowWinRate() then
		if not bee.isNull(self._PKWinRate) then
			GameModel.layer:putEffectItem(self._PKWinRate)
			self._PKWinRate = nil
		end
	else
		local isNew = false
		if bee.isNull(self._PKWinRate) then
			self._PKWinRate = GameModel.layer:playUIEffect("views/table/PK/PKWinRate", self.node.transform, self.ImageWin.transform.localPosition, -1)
			isNew = true
		end
		local info = self.data:getPlayer(self.seatid)
		if info then
			local TextRate = self:find("AnimRoot/TextRate", self._PKWinRate)
			if math.floor(info.win_rate) == info.win_rate then
				bee.setText(TextRate, string.format("%d%%", info.win_rate))
			else
				bee.setText(TextRate, string.format("%d%%", math.floor(info.win_rate)))
			end
			if not isNew then
				TextRate.transform.localScale = bee.v3one
				bee.tween(TextRate)
				: to(0.2, { scale = bee.v3(1.15, 1.15, 1.15) })
				: to(0.2, { scale = bee.v3one })
				: link()
			end
		end
	end
end

function P:getCardWorldPos(index)
	return self.ImageCards[index].transform.position
end

-- 牌局结束后，回收手牌牌
function P:recyclingCards()
	self:showWinNodes(false)
	self:showLoseNodes(false)
    for _, v in ipairs(self.ImageCards) do
        if v.activeSelf then
			self:flopCard(v, 0, function()
				v:SetActive(false)
				local card = self.head.tableLayer:getUiImageCard()
				card.transform.localScale = v.transform.localScale
				card.transform.localEulerAngles = v.transform.localEulerAngles
				card.transform.position = v.transform.position
				bee.setOpacity(card, 1)
				self.head.tableLayer._nodeCache:addUsing(card)
				bee.tween(card, true)
				: to(tpl_constdata.IngameRecyleCardDt, {
					position = self.head.tableLayer.dealCardWorldPos, 
					rotate = bee.v3zero,
					scale = Config.CARD_SCALE_DEAL,
					opacity = 0,
				}, {rotate = DT.RotateMode.FastBeyond360})
				: onComplete(function()
					self.head.tableLayer:_putDealTmpCard(card)
				end)
				: link()
				: setTarget()
			end)
        end
    end
	self.BgHandType:SetActive(false)
	if self.BgHandType2 then
		self.BgHandType2:SetActive(false)
	end
	if self.BgCardValue then
		self.BgCardValue:SetActive(false)
	end
	for _, v in ipairs(self.BgLights) do
		v:SetActive(false)
	end

	self:refreshWinRate()
	if not bee.isNull(self._cardNode) then
		GameModel.layer:putEffectItem(self._cardNode)
		self._cardNode = null
	end
end

