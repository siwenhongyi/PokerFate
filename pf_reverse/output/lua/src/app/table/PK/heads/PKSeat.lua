local P = class("PKSeat", require("app.table.base.SeatNode"))

function P:ctor()
	P.super.ctor(self)
end

function P:onAwake()
	P.super.onAwake(self)

	self.Button = self:find("Button")

	self._tableCard = nil
	self._tableInfo = nil
end

function P:refreshUI()
	P.super.refreshUI(self)
	
	self:refreshButton()
	self:refreshCard()
end

function P:refreshPlayUI(is_reset)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:refreshPlayUI(is_reset)
	end
	self:refreshButton(is_reset)
	self:refreshCard()
end

function P:refreshActionUI(instant)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:refreshActionUI(instant)
		if instant and self._tableCard then
			local info = self.data:getPlayer(self.seatid)
			if info and info.has_card and not info.is_fold then
				self._tableCard:refreshIdle()
			end
		end
	end
end

function P:initPlayer(from_st)
	P.super.initPlayer(self, from_st)
	self:refreshCard()
end

function P:setStatus(status, from_st)
	P.super.setStatus(self, status, from_st)
	
	if self._tableCard then
		self._tableCard:refreshUI()
	end
	if self._tableInfo then
		self._tableInfo:refreshUI()
	end
end

function P:setShowIndex(index, self_index, infoIndex)
	P.super.setShowIndex(self, index, self_index, infoIndex)
	self._tableCard = self.tableLayer.TableCards[infoIndex]
	self._tableCard:setSeatId(self.seatid)

	self._tableInfo = self.tableLayer.TableInfos[infoIndex]
	self._tableInfo:setSeatId(self.seatid)

	self._tableCard:refreshUI()
	self._tableInfo:refreshUI()
	
	-- if self:isMe() then
	-- 	self.ImageButton.transform.localPosition = bee.v3(140, 20)
	-- else
	-- 	-- local x = index < self_index and self.buttonX or -self.buttonX
	-- 	-- self.ImageButton:setPosition(x, self.buttonY)
	-- end
end

function P:refreshButton(is_reset)
	self._tableCard:setButtonVisible(self.data:getDealerIndex() == self.seatid)
	self._tableInfo:setButtonVisible(self.data:getDealerIndex() == self.seatid)
end

function P:getButtonIcon()
	return self._tableInfo:getButtonIcon()
end

function P:refreshEyes()
	if self:isMe() then
		self:emitFunc("refreshEyes")
	end
end

function P:refreshTableTag()
	if self._tableInfo then
		self._tableInfo:refreshTag()
	end
end

function P:refreshCard()
	if self:isMe() then
		self:emitFunc("refreshCard")
	else
		local player = self.data:getPlayer(self.seatid)
		if player.has_card and player.hand_cards and player.hand_cards[1] > 0 then
			self:emitFunc("refreshCard")
			self._tableCard:showCard(false)
		else
			self._tableCard:refreshCard()
		end
	end
end

function P:checkCards()
	local player = self.data:getPlayer(self.seatid)
	if player.on_seat then
		self.playerCls:checkCards(player)
	end
end

function P:showCard(visible, index, isBack)
	if self.status == SEAT_ST.HAS_PLAYER then
		if self:isMe() then
			self.playerCls:showCard(visible, index, isBack)
		else
			local player = self.data:getPlayer(self.seatid)
			if player.has_card and player.hand_cards and player.hand_cards[1] > 0 then
				self.playerCls:showCard(visible, index, isBack)
				self._tableCard:showCard(false)
			else
				self.playerCls:showCard(false)
				return self._tableCard:showCard(visible, index, isBack)
			end
		end
	end
end

function P:showCardForce()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:showCardForce()
	end
end

function P:showCardAndFlop(isDealing)
	if self.status == SEAT_ST.HAS_PLAYER then
		if self:isMe() then
			self.playerCls:showCardAndFlop(isDealing)
		else
			self.playerCls:showCardAndFlop(isDealing)
			self._tableCard:showCard(false)
		end
	end
end

function P:showCardStatus()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:showCardStatus()
	end
end

function P:showCardType(cardType, cards, isDealing, pkType)
	if self.status == SEAT_ST.HAS_PLAYER then
		if self:isMe() then
			self.playerCls:showCardType(cardType, cards, isDealing, pkType)
		else
			self.playerCls:showCardType(cardType, cards, isDealing, pkType)
			-- self._tableCard:showCardType(cardType, cards)
		end
	end
end

function P:foldCard()
	if self.status == SEAT_ST.HAS_PLAYER then
		if self:isMe() then
			self.playerCls:foldCard()
		else
			self.playerCls:foldCard()
			self._tableCard:foldCard()
		end
	end
end

function P:refreshWinRate()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:refreshWinRate()
	end
end

function P:playSound(key)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:playSound(key)
	end
end

function P:playScrap()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:playScrap()
	end
end

function P:stopScrap()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:stopScrap()
	end
end

function P:playUnScrap()
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:playUnScrap()
	end
end

function P:setCardGrep()
	if self.status == SEAT_ST.HAS_PLAYER then
		if self:isMe() then
			self.playerCls:setCardGrep()
		else
			self._tableCard:setCardGrep(true)
		end
	end
end

function P:getDealToPosition(index)
	if self:isMe() and self.playerCls then
		return self.playerCls:getCardWorldPos(index)
	else
		return self._tableCard:getCardPosiiton(index)
	end
	return self.transform.position 
end

function P:getCardWorldPos(index)
	return self.playerCls:getCardWorldPos(index)
end

function P:recyclingCards()
	if self.playerCls then
		self.playerCls:recyclingCards()
	end
	if self._tableCard then
		self._tableCard:recyclingCards()
	end
end

function P:startProgress()
	local duration = self.data:getActionTime()
	self.playerCls:startProgress(duration)
	self.playerCls:emphasizeHead()
end

function P:getCollectBetToPotDt()
	if self.playerCls then
		return self.playerCls:getCollectBetToPotDt()
	end
	return 0
end

function P:collectBetToPot(dt)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:collectBetToPot(dt)
	else
		local info = self.data:getPlayer(self.seatid)
		if info and info.bet_chip > 0 then
			self._tableInfo:collectBetToPot(dt)
		else
			self._tableInfo:showTag()
		end
	end
end

function P:collectPotToHand(chips, cb)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:collectPotToHand(chips, cb)
	end
end

function P:cleanSeatCollectCB()
	if self.playerCls then
		self.playerCls:cleanSeatCollectCB()
	end
end

function P:refreshChip(player, animDt, refreshWhenNoTween)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:refreshChip(player, animDt, refreshWhenNoTween)
	end
end

function P:refreshChipBB(player)
	if self.status == SEAT_ST.HAS_PLAYER then
		self.playerCls:refreshChip(player, nil, true)
		if self._tableInfo then
			self._tableInfo:refreshUI()
		end
	end
end

function P:sitDownCallback()
	UiManager:showUI("PokerBuyin", {seatid = self.seatid, tableInfo = self.data})
end

function P:refreshSittingOut()
	if self.playerCls then
		self.playerCls:refreshSittingOut()
	end
end

function P:refreshAddingChips(is_adding, chips, type)
	if self.playerCls then
		self.playerCls:refreshAddingChips(is_adding, chips, type)
	end
end

return P