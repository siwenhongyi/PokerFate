local PKHelper = require("app.table.PK.PKHelper")
local P = class("PKTable3D", require("app.table.base.TableLayer"))

function P:ctor()
	P.super.ctor(self)
	self.inMain = true
end

function P:setParams(params)
	P.super.setParams(self, params)
end

function P:onAwake()
	P.super.onAwake(self)

	self.TextBlind = self:find("TextBlind")
	self.BgPot = self:find("BgPot")
	self.ImagePot = self:find("Image2", self.BgPot)
	self.TextPot = self:find("BgPot/TextPot")
	self.ImageCard = self:find("ImageCard", self.BgTable)
	self.ImageCardUI = self:find("ImageCardUI")

	self.BgWaitBBTip = self:find("BgWaitBBTip")
	self.BgPayBBTip = self:find("BgPayBBTip")
	self.BgSittingoutTip = self:find("BgSittingoutTip")

	self.ImageCard:SetActive(false)
	self.ImageCardUI:SetActive(false)

	self.Boards, self.Lights = {}, {}
	for i = 1, 5 do
		local card = self:find("BgPublic/ImagePoker_" .. i, self.BgTable)
		self.Boards[i] = card
		self.Lights[i] = self:find("Light", card)
	end
	self.ChipMids = {
		self:find("ChipMid1"),
		self:find("ChipMid2"),
		self:find("ChipMid3"),
		self:find("ChipMid4"),
		self:find("ChipMid5"),
		self:find("ChipMid6"),
	}

	bee.addClick(self:find("PayBBButton", self.BgWaitBBTip), function()
		Game:playSound("ui_button_confirm")
		if bee.checkCd("PKTable_PayBBButton", 1) then
			Net:sendReq("pb.SetWaitBlindTypeREQ", {wait_blind = false})
		end
	end)

	bee.addClick(self:find("WaitBBButton", self.BgPayBBTip), function()
		Game:playSound("ui_button_confirm")
		if bee.checkCd("PKTable_PayBBButton", 1) then
			Net:sendReq("pb.SetWaitBlindTypeREQ", {wait_blind = true})
		end
	end)

	bee.addClick(self:find("SittingoutButton", self.BgSittingoutTip), function()
		Game:playSound("ui_button_confirm")
		if bee.checkCd("PKTable_SittingoutButton", 0.5) then
			Net:sendReq("pb.ReserveSeatREQ", {reserve = false})
		end
	end)
end

function P:onStart()
	P.super.onStart(self)
	self:initTableCards()
	if GameModel.data and not GameModel.data:isRecord() then
		self:_showActionLayer()
	end

	if GuideManager:isInGuide() then
		UiManager:showUI("GameGuide", {guide = GuideManager.curGuide.guide, data = GuideManager.curGuide})
	end

	if GameModel.data then
		local chipIcon = GameModel.data:getChipIcon()
		if chipIcon then
			bee.setIcon(self.ImagePot, chipIcon)
		end
	end

	self:refreshCardBack()
end

function P:onDestroy()
    P.super.onDestroy(self)
	if self._winnerAction then
		self._winnerAction:Kill()
		self._winnerAction = nil
	end
end

function P:onEnable()
	if not GameModel.data then
		return
	end
	if not GameModel.data:isRecord() then
		if GameModel.data:isFriendsRoom() then
			self.uiLayer = UiManager:showUI("PKFriendsRoomLayer")
		elseif GameModel.data:isSNG() then
			self.uiLayer = UiManager:showUI("TournamentSNGUILayer")
		else
			self.uiLayer = UiManager:showUI("PKUILayer")
		end
		self:_showActionLayer()
	else
		self.uiLayer = UiManager:showUI("PKUIRecordLayer", {data = GameModel.data:getRecord()})
	end
end

function P:_showActionLayer()
	if not self.actionLayer then
		local actLayer = GameModel.data:isAllinOrFold() and "PKActionAllinLayer" or "PKActionLayer"
		self.actionLayer = UiManager:showUI(actLayer, {
			data = GameModel.data,
			tableLayer = self,
			zOrder = self.uiLayer and (self.uiLayer.zOrder + 1) or nil,
		})
	end
end

function P:onDisable()
	UiManager:hideUI("PKFriendsRoomLayer")
	UiManager:hideUI("PKUILayer")
	UiManager:hideUI("PKActionLayer")
	self.actionLayer = nil
end

function P:initTableCards()
	self.TableCards = {}
	self.TableInfos = {}
	for i = 1, 6 do
		self.TableCards[i] = ObjectPool:getCls(self:find("TableCard" .. i, self.BgTable))
		self.TableCards[i]:setIndex(i)

		self.TableInfos[i] = ObjectPool:getCls(self:find("TableInfo" .. i))
		self.TableInfos[i]:setIndex(i)
	end
end

function P:refreshCardBack()
	local cardBackImage = PlayerModel:getCurCardBackImage()
	bee.setIcon(self.ImageCardUI, cardBackImage)
	bee.setSpriteImg(self.ImageCard, cardBackImage)
	-- for _, v in ipairs(self.Boards) do
	-- 	bee.setSpriteImg(v, cardBackImage)
	-- end
end

-- function P:onShow()
-- 	self:refreshUI()
-- end

function P:refreshSeatPosition()
	P.super.refreshSeatPosition(self)
	
	if nil == self.seat5Position then
		self.seat2Position = {self.seatPosition[6], self.seatPosition[3]}
		self.seat3Position = {self.seatPosition[1], self.seatPosition[3], self.seatPosition[5]}
		self.seat4Position = {self.seatPosition[1], self.seatPosition[3], self.seatPosition[5], self.seatPosition[6]}
		self.seat5Position = clone(self.seatPosition)
	end
	if 2 == self.seatNum then
		self.seatInfoIndexes = {6, 3}
		self.seatPosition = {self.seatPosition[6], self.seatPosition[3]}
	elseif 3 == self.seatNum then
		self.seatInfoIndexes = {1, 3, 5}
		self.seatPosition = {self.seatPosition[1], self.seatPosition[3], self.seatPosition[5]}
	elseif 4 == self.seatNum then
		self.seatInfoIndexes = {1, 3, 5, 6}
		self.seatPosition = {self.seatPosition[1], self.seatPosition[3], self.seatPosition[5], self.seatPosition[6]}
	else
		-- self.seatPosition = self.seat5Position
	end
end

function P:refreshUI()
	P.super.refreshUI(self)
	-- for _, v in ipairs(self.TableCards) do
	-- 	v:refreshUI()
	-- end
	self:resetCards()
	self:refreshBlind()
	self:refreshPot()
	self:refreshBoard()
	if self.data:isAllAllin() then
		self.data:calculateWinOdds()
	end
	self:refreshCardType()
	self:stopCd()
	self:refreshTips()
	self:refreshWaitingPlayerTip()
	self:refreshSettingout()
	if self.actionLayer then
		self.actionLayer:refreshUI()
	end
	-- self.DealCardPosNode:stopAllActions()
	self.dealBoardDealy = 0
	scheduler:removeTarget(self.node)
	if self._winnerAction then
		self._winnerAction:Kill()
		self._winnerAction = nil
	end
end

function P:resetCards()
	self._nodeCache:resetInUsings(true)
end

function P:refreshBlind()
	bee.emit(EventDef.evt_refreshBlind)
end

function P:refreshPot(animDt)
	if self._showPotTween then
		self._showPotTween:Kill()
		self._showPotTween = nil
	end
	local pot = self.data:getPotInfo()
	if pot == 0 then
		self.BgPot:SetActive(false)
		self._showPot = 0
	else
		self.BgPot:SetActive(true)
		if self._showPot and animDt and animDt > 0 then
			self._showPotTween = bee.Tween.toFloat(self._showPot, pot, animDt, function(v)
				bee.setText(self.TextPot, self.data:getBetChipsStr(math.floor(v)))
			end)
		else
			bee.setText(self.TextPot, self.data:getBetChipsStr(pot))
		end
		self._showPot = pot
	end
end

function P:getBgPot()
	return self.ImagePot
end

function P:refreshBoard(index, notIsLight)
	local board = self.data:getBoardInfo()
	for i, v in ipairs(self.Boards) do
		if index and i > index then break end

		if not notIsLight then
			self.Lights[i]:SetActive(false)
		end
		bee.setColor(v, COLOR.main_white, "SpriteRenderer")
		local code = board[i]
		if code then
			v:SetActive(true)
			bee.setSprite(v, GF.getCardImageByCode(code))
		else
			v:SetActive(false)
		end
	end
end

function P:refreshCardType(isDealing)
	for k, v in ipairs(self.data:getAllPlayers()) do
		if not self.data:isPlaying() then
			self.seatController[k]:refreshCard()
		elseif v.has_card and v.hand_cards and v.hand_cards[1] and v.hand_cards[2] then
			local cards, cardType, pkType = PKHelper.getCardType(v.hand_cards, self.data:getBoardInfo(), self.data:getRoomType())
			self.seatController[k]:showCardType(cardType, cards, isDealing, pkType)

			local board = self.data:getBoardInfo()
			
			if #board > 0 and v:isMe() and pkType and pkType >= tpl_constdata.IngameTipType then
				local codes = {}
				for k, v in pairs(cards) do
					local code = GF.getCardCode(v.number, v.color)
					codes[code] = code
				end
				
				for i, v in ipairs(board) do
					local Light = self.Lights[i]
					if codes[v] then
						Light:SetActive(true)
					else
						Light:SetActive(false)
					end
				end
			end
		end
	end
end

function P:refreshTips()
	self:refreshWaitTip()
end

function P:updateCD(left_time)
	self.data:setWaitNextHand(false)
	
	bee.Tween.killByTarget(self.BgTip)

	if self.data:getOnSeatNum() < 2 then
		-- self.BgTip:SetActive(false)
		self:refreshWaitingPlayerTip()
		return
	end

	if left_time <= 3 then
		-- local tips = _F("LAB_NEXT_ROUND_CD", left_time)
		-- self:showTips(tips)
		-- self.BgTip:SetActive(left_time <= 3)
		UiManager:hideUI("ActivityPokerGuessFast")
	end
	if left_time >= 1 then
		self:once(1, function()
			self:updateCD(left_time - 1)
		end)
		self.data:setWaitNextHand(true)
	end
end

function P:stopCd()
	self.BgTip:SetActive(false)
	bee.Tween.killByTarget(self.BgTip)
	self:refreshWaitingPlayerTip()
end

function P:evt_SitDownRSP(event)
	P.super.evt_SitDownRSP(self, event)
	self:refreshWaitingPlayerTip()
	self:refreshSettingout()
end

function P:evt_OtherLeaveRoomBRC(msg)
	if self.data:isTableGameOver() then
		self:tryAutoSwitchTable()
	end
end

function P:onStandUpBrc(event)
	P.super.onStandUpBrc(self, event)
	self:refreshWaitingPlayerTip()
end

function P:refreshWaitingPlayerTip()
	if not self.data:isSNG() and not self.data:isMTT() then
		if self.data:isMeOnSeat() then
			if self.data:getOnSeatNum() == 1 then
				self.BgWaitBBTip:SetActive(false)
				self.BgPayBBTip:SetActive(false)
				self:showTips("LAB_WAIT_FOR_PLAYER")
			elseif self.data:isPlaying() and not self.data:isMePlaying() then
				self.data:setWaitNextHand(true)
				local player = self.data:getMyPlayerInfo()
				if player and player.wait_blind_type == 0 then
					self:showTips()
					self.BgWaitBBTip:SetActive(false)
					self.BgPayBBTip:SetActive(true)
				elseif player and player.wait_blind_type == 1 then
					self:showTips()
					self.BgWaitBBTip:SetActive(true)
					self.BgPayBBTip:SetActive(false)
				else
					self:showTips("LAB_WAIT_NEXT_HAND")
				end
			else
				self:showTips()
				self.BgWaitBBTip:SetActive(false)
				self.BgPayBBTip:SetActive(false)
			end
		else
			self:showTips()
			self.BgWaitBBTip:SetActive(false)
			self.BgPayBBTip:SetActive(false)
		end
	else
		self:showTips()
		self.BgWaitBBTip:SetActive(false)
		self.BgPayBBTip:SetActive(false)
	end
end

function P:refreshSettingout()
	self.BgSittingoutTip:SetActive(self.data:isMeSittingOut())
	if self.data:isMeSittingOut() then
		self.BgSittingoutTip.transform:SetAsLastSibling()
	end
end

function P:evt_DealerInfoRSP()
	-- UiManager:hideUI("IngameNoticeSave")
	self._isDealingHands = nil
	local from, to = nil, nil
	for i, v in ipairs(self.seatController) do
		local ImageButton = v:getButtonIcon()
		if ImageButton.activeSelf then
			from = ImageButton
		end
		if self.data:getDealerIndex() == v.seatid then
			to = ImageButton
		end
		v:refreshPlayUI(true)
		v:stopScrap()
	end
	if from and to and from ~= to then
		local ImageButton = self._nodeCache:getItem("ImageButton", from, self.transform)
		self._nodeCache:addUsing(ImageButton)
		ImageButton:SetActive(true)
		ImageButton.transform.position = from.transform.position
		to:SetActive(false)
		bee.tween(ImageButton, true)
		: to(0.2, {position = to.transform.position})
		: onComplete(function()
			self._nodeCache:removeUsing(ImageButton)
			self._nodeCache:putItem(ImageButton)
			to:SetActive(true)
		end)
		: link()
	end
	self:refreshPot()
	self:refreshBoard()
	self:stopCd()
	-- self:showTips("LAB_STARTING_GAME")
	if self.data:getDealerIndex() == self.data:getMyPosition() then
		self.seatController[self.data:getDealerIndex()]:playSound(ROLE_VOICE.dealer_turn)
	end

	for _, v in ipairs(self.seatController) do
		local player = self.data:getPlayer(v.seatid)
		if player then
			v:refreshChip(player, nil, true)
		end
	end
end

function P:evt_TableGameOverRSP(msg)
	for _, v in ipairs(self.seatController) do
		v:refreshPlayUI(true)
	end
	self:refreshPot()
	self:refreshBoard()
	self:stopCd()

	if msg.type == 3 then
		self:tryAutoSwitchTable()
	end
end

function P:evt_HandCardRSP(msg)
	-- P.super.evt_HandCardRSP(self, msg)
	self:refreshWaitTip()
	local myPosition = self.data:getMyPosition()
	local seat = self.seatController[myPosition]
	if seat then
		seat:refreshCard()
		if not self._isDealingHands then
			seat:showCard(true)
		end
	end
	self:stopCd()
	-- self:showTips("LAB_STARTING_GAME")
end

function P:runDealAction(func, delay)
	self:once(delay, func)
end

function P:tryAutoSwitchTable()
	if not self.data:isTournament() and not self.data:isFriendsRoom() and SettingModel:isAutoSwitch() then
		if self.data:isMeOnSeat() then
			if self.data:getOnSeatNum() == 1 then
				GameModel:switchTable()
			end
		end
	end
end

function P:tryShowFastGuess()
	-- if G.userMgr:isNewUserGuideEnd() and self.data:isCanGuess() and not G.ccsMgr:isCCSUIShowing("ActivityPokerGuess") and G.userMgr:isAutoPokerGuess() then
	-- 	self.rootNode:runAction(cc.CallFunc:create(function()
	-- 		UiManager:showUI("ActivityPokerGuessFast")
	-- 	end))
	-- end
end

function P:getTableImageCard()
	return self._nodeCache:getItem("Table_ImageCard", self.ImageCard, self.BgTable.transform)
end

function P:getUiImageCard()
	return self._nodeCache:getItem("Ui_ImageCard", self.ImageCardUI, self.transform)
end

function P:_popDealTmpCard()
	local card = self:getTableImageCard()
	self._nodeCache:addUsing(card)
	card.transform.localEulerAngles = bee.v3zero
	card:SetActive(true)
	card.transform.position = self.dealCardWorldPos
	card.transform.localScale = Config.CARD_SCALE_DEAL
	bee.setOpacity(card, 1, "SpriteRenderer")
	return card
end

function P:_putDealTmpCard(card)
	self._nodeCache:removeUsing(card)
	self._nodeCache:putItem(card)
end

function P:dealPlayerCard()
	local dealerIndex = self.data:getDealerIndex()
	local seatNum = self.data:getSeatNum()
	local dealList = {}
	for i = 1, seatNum do
		local seatid = dealerIndex + i
		if seatid > seatNum then
			seatid = seatid - seatNum
		end
		local player = self.data:getPlayer(seatid)
		if player and player.action_type == POKER_ACTION.WAIT and player.chips > 0 then
			dealList[#dealList + 1] = seatid
			player.has_card = true	-- 给回放设置有牌标志
		end
	end
	if #dealList == 0 then
		return
	end
	self._isDealingHands = true
	local handCardNum = self.data:getHandCardNum()
	local action_time, delay = tpl_constdata.IngameDealFlyDt, tpl_constdata.IngameDealIntervalDt
	if handCardNum >= 4 then
		action_time, delay = action_time / 2, delay / 2
	end
	local myPosition = self.data:getMyPosition()
	local rotates = handCardNum >= 4 and Config.CARD_ROTATE_HANDS_OMAHA or Config.CARD_ROTATE_HANDS
	local function dealPlayerCard(cardIndex, dealIndex)
		Game:playSound("ui_dealing_cards_2")
		local seatid = dealList[dealIndex]
		local card = self:_popDealTmpCard()
		
		local scale = seatid == myPosition and Config.CARD_SCALE_TO_HAND or Config.CARD_SCALE_TO
		bee.tween(card, true)
		: to(action_time, {position = self.seatController[seatid]:getDealToPosition(cardIndex), rotate = rotates[cardIndex], scale = scale}, {rotate = DT.RotateMode.FastBeyond360})
		: call(function()
			self.seatController[seatid]:showCard(true, cardIndex, true)
			if seatid == myPosition and cardIndex >= handCardNum then
				self.seatController[seatid]:showCardAndFlop(true)
			end
			if dealIndex == #dealList and cardIndex >= handCardNum then
				if self.dealer then
					self.dealer:showChangeTip(false)
				end
				Net:sendReq("pb.RoundStartDisplayFinishREQ", {gameid = self.data:getGameId(), stage = POKER_ROUND.PRE_FLOP})
			end
			self:_putDealTmpCard(card)
		end)
		: link()
		: setTarget()

		self:once(delay, function()
			local dealIndex = dealIndex + 1
			local cardIndex = cardIndex
			if dealIndex > #dealList then
				dealIndex = dealIndex - #dealList
				cardIndex = cardIndex + 1
				if cardIndex > handCardNum then
					-- self:refreshCardType()
					self:refreshWaitingPlayerTip()
					-- self._isDealingHands = nil
					return
				end
			end
			dealPlayerCard(cardIndex, dealIndex, 0)
		end)
	end
	self:runDealAction(function()
		dealPlayerCard(1, 1) 
		-- self:showTips("LAB_DEALING_CARD")
	end, 1 + (self.data:getAntiActionDt() or 0))
end

function P:evt_RoundStartBRC(params)
	for _, v in ipairs(self.seatController) do
		v:refreshActionUI(true)
	end
	if self._winnerAction then
		self._winnerAction:Kill()
		self._winnerAction = nil
	end
	local stage = params.stage
	if stage == POKER_ROUND.PRE_FLOP then
		self:dealPlayerCard()
		self:cleanSeatCollectCB()
		return
	end

	self:resetCards()
	self:refreshPot()
	self:stopCd()
	self:refreshTips()
	self:refreshWaitingPlayerTip()
	if self.actionLayer then
		self.actionLayer:refreshUI()
	end
	scheduler:removeTarget(self.node)

	local board = params.board
	local action_time, delay = tpl_constdata.IngameBoardFlyDt, tpl_constdata.IngameBoardIntervalDt
	local isAllAllin = self.data:isAllAllin()
	if isAllAllin then
		delay = delay + tpl_constdata.IngameAllinDealCardDt
	end
	local function dealBoard(index, total, count)
		if count == 2 or count == 3 then
			Game:playSound("ui_dealing_cards_2")
		else
			Game:playSound("ui_dealing_cards_1")
		end
		local target = self.Boards[index + count]
		local card = self:_popDealTmpCard()

		if isAllAllin then
			self.data:calculateWinOdds(index + count)
		end
		
		local code = board[count + 1]
		bee.tween(card, true)
		: to(action_time, {position = target.transform.position, rotate = Config.CARD_ROTATE_180, scale = bee.v3(0.44, 0.44, 0.44)}, {rotate = DT.RotateMode.FastBeyond360})
		: call(function()
			target:SetActive(true)
			self:find("Light", target):SetActive(false)
			bee.setSprite(target, GF.getCardImageByCode(code))
			
			self:_putDealTmpCard(card)
			if count + 1 >= total then
				if index == 5 and isAllAllin and (GuideManager:isInGuide() or not self.data:isHaveSurelyWinner()) then
					bee.setSprite(target, GF.getCardImageByCode(0))
					local eft = self:playUIEffect("Prefab/PKTable/Eff_poker_allin_sololight", self.transform, nil, 4)
					eft.transform.position = target.transform.position
					local gameid = self.data:getGameId()
					Game:playSound("ui_all_in_last")
					bee.once(1.6, function()
						if gameid == self.data:getGameId() then
							bee.setSprite(target, GF.getCardImageByCode(code))
							self:refreshCardType(true)
							Net:sendReq("pb.RoundStartDisplayFinishREQ", {gameid = self.data:getGameId(), stage = stage})
						end
					end, eft)
				else
					self:refreshCardType(true)
					Net:sendReq("pb.RoundStartDisplayFinishREQ", {gameid = self.data:getGameId(), stage = stage})
				end
			elseif isAllAllin then
				-- self:refreshCardType(true)
				for k, v in ipairs(self.data:getAllPlayers()) do
					if v.hand_cards and v.hand_cards[1] and v.hand_cards[2] then
						self.seatController[k]:refreshWinRate()
					end
				end
			end
		end)
		: link()
		: setTarget()
		
		if count + 1 >= total then
			return
		end
		self:once(delay, function ()
			dealBoard(index, total, count + 1)
		end)
	end
	if stage == POKER_ROUND.FLOP then
		self:runDealAction(function() dealBoard(1, 3, 0) end, self.dealBoardDealy)
	elseif stage == POKER_ROUND.TURN then
		self:refreshBoard(3)
		self:runDealAction(function() dealBoard(4, 1, 0) end, self.dealBoardDealy)
	elseif stage == POKER_ROUND.RIVER then
		self:refreshBoard(4)
		self:runDealAction(function() dealBoard(5, 1, 0) end, self.dealBoardDealy)
	end
	self.dealBoardDealy = 0
end

function P:evt_ActionNotifyBRC(msg)
	local index = self.data:getActionIndex()
	if index == self.data:getMyPosition() then
		if msg.pre_action_result == 2 then
		else
			Game:playSound("action_tip")
			bee.emit(EventDef.evt_hideUiWhenAction, false)
		end
	end
	for i, v in ipairs(self.seatController) do
		if i == index then
			if v:isMe() then
				if msg.pre_action_result == 2 then
				else
					v:startProgress()
				end
				if not self._isDealingHands then
					v:showCardForce()
				end
			else
				v:startProgress()
			end
		else
			v:stopProgress(true)
		end
	end
	self:checkPokers()
	self._isDealingHands = nil
end

function P:evt_ActionBRC(msg)
	local seatid = msg.seatid + 1
	local player = self.data:getPlayer(seatid)
	local action_type = msg.action_type
	if GF.isFoldAction(msg.action_type) then
		-- self.seatController[seatid]:playScrap()
		self.seatController[seatid]:refreshActionUI(true)
		self.seatController[seatid]:foldCard()
		if seatid == self.data:getMyPosition() then
			self.seatController[seatid]:playSound(ROLE_VOICE.fold)
		else
			Game:playSound("ui_fold_cards")
		end
	elseif action_type == POKER_ACTION.CHECK or action_type == POKER_ACTION.SYS_CHECK then
		self.seatController[seatid]:playSound(ROLE_VOICE.check)
	elseif GF.isBetAction(action_type) then
		self.data:setWaitNextHand(false)
		if player.chips == 0 or action_type == POKER_ACTION.ALLIN then
			self.seatController[seatid]:playSound(ROLE_VOICE.all_in)
			if msg.chips >= tpl_constdata.PokerAllInAnimBB * self.data:getBigBlind() then
				UiManager:showUI(GameModel:getAllinUiName(player.allin_eff), {multi = true, seatid = seatid, zOrder = self.actionLayer and self.actionLayer.zOrder + 1})
			end
			self.seatController[seatid]:emitFunc("showAllin")
		else
			if action_type == POKER_ACTION.CALL then
				if msg.chips == self.data:getLastPotNum() then
					self.seatController[seatid]:playSound(ROLE_VOICE.pot)
				else
					self.seatController[seatid]:playSound(ROLE_VOICE.call)
				end
			elseif action_type == POKER_ACTION.RAISE then
				if msg.chips < player.bet_chip then
					self.seatController[seatid]:playSound(ROLE_VOICE.reRaise)
				elseif msg.chips == self.data:getLastPotNum() then
					self.seatController[seatid]:playSound(ROLE_VOICE.pot)
				else
					self.seatController[seatid]:playSound(ROLE_VOICE.raise)
				end
			elseif action_type == POKER_ACTION.BET then
				self.seatController[seatid]:playSound(ROLE_VOICE.bet)
			elseif action_type == POKER_ACTION.SB then
				if player:isMe() then
					self.seatController[seatid]:playSound(ROLE_VOICE.sb)
				end
			elseif action_type == POKER_ACTION.BB or action_type == POKER_ACTION.FORCE_BB then
				if player:isMe() then
					self.seatController[seatid]:playSound(ROLE_VOICE.bb)
				end
			-- elseif action_type == POKER_ACTION.ANTE then
			-- 	self.seatController[seatid]:playSound(ROLE_VOICE.ante)
			end
		end
		self.dealBoardDealy = 0.3
	end
	if not GF.isFoldAction(msg.action_type) then
		self.seatController[seatid]:refreshActionUI(true)
	end
	if player:isMe() then
		bee.emit(EventDef.evt_hideUiWhenAction, true)
	end
end

function P:cleanSeatCollectCB()
	for _, v in ipairs(self.seatController) do
		v:cleanSeatCollectCB()
	end
end

function P:evt_RoundOverBRC()
	local collectDt = 0
	for _, v in ipairs(self.seatController) do
		local dt = v:getCollectBetToPotDt()
		if collectDt < dt then
			collectDt = dt
		end
	end
	local bet_chip = 0
	for i, v in ipairs(self.seatController) do
		v:collectBetToPot(collectDt)
		local player = self.data:getPlayer(i)
		bet_chip = math.max(bet_chip, player.bet_chip)
	end
	self:once(0.53 + collectDt, function ()
		self:refreshPot(collectDt + 0.2)
	end)
	if self.data:isInAnte() then
		self.data:setAntiActionDt(0.5)
		self.data:setIsInAnte(false)
	else
		self.data:setAntiActionDt(nil)
	end

	if bet_chip > self.data:getBigBlind() * 200 then
		Game:playSound("ui_chips_bet_3")
	elseif bet_chip >= self.data:getBigBlind() * 40 then
		Game:playSound("ui_chips_bet_2")
	else
		Game:playSound("ui_chips_bet_1")
	end
end

function P:evt_WinnerRSP(params)
	self.BgPot:SetActive(false)
	if self._needShowLight then
		for i, v in ipairs(self.seatController) do
			-- v:setCardGrep()
		end
	end
	local winner_info, winners = {}, {}
	for _, info in ipairs(params.winner) do
		local seatid = info.seatid + 1
		local chips = info.chips
		if winner_info[seatid] then
			winner_info[seatid] = winner_info[seatid] + chips
		else
			winner_info[seatid] = chips
		end
		if self._needShowLight then
			self:showWinCardLight(seatid)
			winners[seatid] = seatid
		end
	end
	if self._needShowLight then
		for i, v in ipairs(self.seatController) do
			if not winners[i] then
				v:emitFunc("showLoseNodes", true)
				-- v:playScrap()
			end
		end
	end

	local myPosition = self.data:getMyPosition()
	local seqs = {}
	local gameid, roomid, tid = self.data:getGameId(), self.data:getRoomId(), self.data:getTid()
	if self._needShowLight then
		local seatid, poolid, chips, msg = nil, nil, 0, nil
		local uid = PlayerModel:getUid()
		-- 先找我
		for _, v in ipairs(params.winner) do
			if v.seatid + 1 == myPosition then
				seatid, chips = v.seatid, chips + v.chips
			end
		end
		if seatid and chips and chips <= self.data:getMyPlayerInfo().begin_chips then
			for _, v in ipairs(params.profit) do
				if v.seatid == seatid then
					if v.chips <= 0 then
						seatid = nil
					end
					break
				end
			end
		end
		if not seatid then
			for _, v in ipairs(params.winner) do
				if not seatid then
					seatid, poolid, chips = v.seatid, v.poolid, chips + v.chips
					uid = v.uid
				elseif seatid == v.seatid then
					chips = chips + v.chips
				elseif v.poolid == poolid then
					seatid = nil
					break
				end
			end
		end
		if seatid then
			local boards, player = self.data:getBoardInfo(), self.data:getPlayerByUid(uid)
			if not player then
				player = self.data:getPlayerByUidOld(uid)
			end
			if player then
				local hand_cards = player.hand_cards
				for _, v in ipairs(params.profit) do
					if v.seatid == seatid then
						msg = v
						break
					end
				end
				seqs[#seqs + 1] = function()
					UiManager:showUI("IngameResult", {
						boards = boards, player = player, hand_cards = hand_cards,
						seatid = seatid + 1, chips = chips, msg = msg
					})
				end
				seqs[#seqs + 1] = tpl_constdata.IngameResultDt
			end
		end
	end
	local needShowLight = self._needShowLight
	seqs[#seqs + 1] = function()
		if needShowLight then
			for _, v in ipairs(params.profit) do
				if v.chips < 0 then
					local seatid = v.seatid + 1
					local player = self.data:getPlayer(seatid)
					if player and player.uid == v.uid and not player.is_fold then
						self.seatController[seatid]:playScrap()
					end
				elseif v.chips > 0 and self.data:isCanScrop(v.chips) then
					local seatid = v.seatid + 1
					local player = self.data:getPlayer(seatid)
					if player then
						SettingModel:setScrapPlayer(self.data, player.uid, nil)
					end
					self.seatController[seatid]:playUnScrap()
				end
			end
		else
			for _, v in ipairs(params.profit) do
				if v.chips > 0 and self.data:isCanScrop(v.chips) then
					local seatid = v.seatid + 1
					local player = self.data:getPlayer(seatid)
					if player then
						SettingModel:setScrapPlayer(self.data, player.uid, nil)
					end
					self.seatController[seatid]:playUnScrap()
				end
			end
		end
		local winSeatId, winChips = nil, 0
		for seatid, chips in pairs(winner_info) do
			if not winSeatId or winChips < chips then
				winSeatId = seatid
				winChips = chips
			end
			local player = self.data:getPlayer(seatid)
			player.chips = player.chips + chips
			if seatid == myPosition then
				Game:playSound("cheer")
				bee.vibrate(tpl_vibrate.button)
			end
			self.seatController[seatid]:collectPotToHand(chips)
		end
		if not needShowLight and winSeatId then
			self.seatController[winSeatId]:playSound(ROLE_VOICE.win2)
		end
	end
	seqs[#seqs + 1] = tpl_constdata.IngameWinPotDt - 0.8
	seqs[#seqs + 1] = function()
		self._winnerAction = nil
		if not self.data:isRecord() then
			for i, v in ipairs(self.seatController) do
				v:recyclingCards()
			end
			if self.data:getGameId() == gameid and not GuideManager:isInGuide() then
				self.data:clearPlayerCards()
			end
			
			local action_time, delay = 0.4, 0.1
			self:once(delay, function()
				for _, v in ipairs(self.Boards) do
					if v.activeSelf then
						v:SetActive(false)
						local card = self:_popDealTmpCard()
						card.transform.localScale = bee.v3one
						card.transform.position = v.transform.position
						bee.tween(card, true)
						: to(action_time, {
							position = self.dealCardWorldPos, 
							rotate = Config.CARD_ROTATE_180, 
							scale = bee.v3(0.44, 0.44, 0.44),
							opacity = 0,
						}, {rotate = DT.RotateMode.FastBeyond360, opacity = "SpriteRenderer"})
						: onComplete(function()
							self:_putDealTmpCard(card)
						end)
						: link()
						: setTarget()
					else
						break
					end
				end
			end)
		end
	end
	self._winnerAction = bee.Tween.sequence(seqs)

	self._needShowLight = nil
	for i, v in ipairs(self.seatController) do
		local player = self.data:getPlayer(i)
		player.bet_chip = 0
		v:refreshActionUI()
	end

	self:updateCD(5)
end

function P:evt_ChipsBackBRC(params)
	local seatid = params.seatid + 1
	local chips = params.chips
	local player = self.data:getPlayer(seatid)
	self.seatController[seatid]:refreshChip(player)
end

function P:showWinCardLight(seatid)
	local boards = self.data:getBoardInfo()
	local player = self.data:getPlayer(seatid)
	local cards, cardType, pkType = PKHelper.getCardType(player.hand_cards, boards, self.data:getRoomType())
	if cards then
	end
	self.seatController[seatid]:showCardType(cardType, cards, nil, pkType)
	self.seatController[seatid]:emitFunc("showWinNodes", true)
end

function P:evt_ShowHandRSP(msg)
	self._needShowLight = true
	local boards = self.data:getBoardInfo()
	local myPosition = self.data:getMyPosition()
	
	if self.data:isAllAllin() then
		self.data:calculateWinOdds()
	end
	for _, v in ipairs(msg.info) do
		local seatid = v.seatid + 1
		local player = self.data:getPlayer(seatid)
		if seatid ~= myPosition then
			self.seatController[seatid]:showCardAndFlop()
		end

		local cards, cardType, pkType = PKHelper.getCardType(player.hand_cards, boards, self.data:getRoomType())
		self.seatController[seatid]:showCardType(cardType, cards, nil, pkType)
	end
end

function P:evt_ShowMyCardRSP(msg)
	if msg.gameid == self.data:getGameId() then
		local seat = self.seatController[self.data:getMyPosition()]
		if seat then
			seat:refreshEyes()
		end
	end
end

function P:evt_ShowMyCardBRC(msg)
	-- self._needShowLight = true
	local boards = self.data:getBoardInfo()
	local myPosition = self.data:getMyPosition()
	for _, v in ipairs(msg.info) do
		local seatid = v.seatid + 1
		local player = self.data:getPlayer(seatid)
		if seatid ~= myPosition then
			self.seatController[seatid]:showCardAndFlop()
		end

		local cards, cardType = PKHelper.getCardType(player.hand_cards, boards, self.data:getRoomType())
		self.seatController[seatid]:showCardType(cardType)

		self.seatController[seatid]:showCardStatus()
	end
end

function P:evt_GetCardsRSP(event)
	self:refreshBoard()
	local me = self.data:getMyPlayerInfo()
	if me then
		self.seatController[self.data:getMyPosition()]:refreshCard()
	end
end

-- 检查是否缺牌了
function P:checkPokers()
	local stage = self.data:getRoundStage()
	local boardNum = 0
	if stage == POKER_ROUND.FLOP then
		boardNum = 3
	elseif stage == POKER_ROUND.TURN then
		boardNum = 4
	elseif stage == POKER_ROUND.RIVER then
		boardNum = 5
	end
	if #self.data:getBoardInfo() ~= boardNum then
		Net:sendReq("pb.GetCardsREQ", {})
		return
	elseif boardNum > 0 then
		for i = 1, boardNum do
			if not self.Boards[i].activeSelf then
				self:refreshBoard(nil, true)
				break
			end
		end
	end
	local info = self.data:getMyPlayerInfo()
	if nil ~= info and info.has_card then
		if nil == info.hand_cards or not info.hand_cards[1] or not info.hand_cards[2] then
			Net:sendReq("pb.GetCardsREQ", {})
		else
			self.seatController[self.data:getMyPosition()]:checkCards()
		end
	end
end

function P:evt_SeatStatusBRC(msg)
	self:refreshSettingout()
end

function P:evt_NoticeRebyRSP(msg)
	if msg then
		local seatid = msg.seatid + 1
		if seatid == self.data:getMyPosition() then
			local data = GF.getTableDataBySB(self.data:getGameType(), self.data:getSmallBlind())
			if data then
				if self.data:isFriendsRoom() then
					UiManager:showUI("FriendsRoomByin")
				elseif (data.min_byin or data.byin) <= PlayerModel:getGold() then
					UiManager:showUI("LobbyByinDialog", {data = data, isReby = true})
				else
					QuickByModel:checkInsideGame(data.gameType, data.quick_buy)
					-- UiManager:showUI("IngameQuickBy", {data = data, dt = msg.reby_left_time})
				end
			else
				printError("NoticeRebyRSP no table data for sb: " .. self.data:getSmallBlind())
			end
		else
			self.seatController[seatid]:refreshAddingChips(true)
		end
	end
end

function P:evt_RebyBRC(msg)
	if msg then
		if msg.code ~= 0 then
			-- Net:sendReq("pb.StandUpREQ", {});
		else
			local seatid = msg.seatid + 1
			local player = self.data:getPlayer(seatid)
			if player then
				self.seatController[seatid]:refreshChip(player)
			end

			if seatid ~= self.data:getMyPosition() then
				self.seatController[seatid]:refreshAddingChips(false, msg.chips, msg.type)
			end
		end
	end
end

function P:evt_SetWaitBlindTypeRSP(msg)
	if msg.code == 0 then
		self:refreshWaitingPlayerTip()
	end
end

function P:evt_refreshShowBB()
	self:refreshPot()

	for _, v in ipairs(self.seatController) do
		local player = self.data:getPlayer(v.seatid)
		if player then
			v:refreshChipBB(player)
		end
	end
end

function P:evt_SelfUserInfoRSP(msg)
	self:refreshCardBack()
end

function P:evt_lan_mod()
	self:refreshWaitingPlayerTip()

	if self.data:isMePlaying() then
		local info = self.data:getMyPlayerInfo()
		if info and info.hand_cards and info.hand_cards[1] and info.hand_cards[2] then
			local cards, cardType, pkType = PKHelper.getCardType(info.hand_cards, self.data:getBoardInfo(), self.data:getRoomType())
			self.seatController[self.data:getMyPosition()]:showCardType(cardType, cards, false, pkType)
		end

		for _, v in ipairs(self.seatController) do
			v:refreshTableTag()
		end
	end

	if self.actionLayer then
		self.actionLayer:hideUI()
		self.actionLayer = nil
	end
	self:_showActionLayer()
	self.actionLayer:refreshUI()
end

return P