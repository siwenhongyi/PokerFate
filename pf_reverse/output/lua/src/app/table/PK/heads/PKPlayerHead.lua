local P = class("PkPlayerHead", require("app.table.base.TableHead"))
local TMP_BET_Z_ORDER = 10

function P:ctor()
	P.super.ctor(self)
	self.in_hand_to_bet = false
	self.betToPotCB = nil
	self.in_bet_to_pot = false
	self.potToHandCB = nil
	self.profitAniScale = 3
	self._needScalePlayer = true
end

function P:onAwake()
	P.super.onAwake(self)
	self.BgBet = self:find("BgBet")
	self.BgBet:SetActive(false)
	self.BgAllin = self:find("BgAllin", self.BgRole)

	self.BgCard = self:find("BgCard")
	self.BgCardPostion = self.BgCard.transform.localPosition
	self.BgStatus = self:find("BgStatus")
	self.BgStatus:SetActive(false)
	
	self.Button = self:find("Button")
	bee.addClick2(self.Button, function()
		Game:playSound("ui_button_confirm")
		local info = self.data:getPlayer(self.seatid)
		UiManager:showUI("InformationMain", {uid = info.uid, from = "table"})
    	bee.logEvent("ingame-profile", GameModel.data:getGameType(), GameModel.data:getRoomId())
	end)
	bee.addClick2(self:find("ButtonChip"), function()
		SettingModel:setShowBB(not SettingModel:isShowBB())
	end)
end

function P:setSeatNode(seat)
	self._seatNode = seat
end

function P:setShowIndex(index, self_index, infoIndex)
	P.super.setShowIndex(self, index, self_index, infoIndex)
	self.BgCard.transform.localPosition = index >= self_index and self.BgCardPostion or bee.v3(-self.BgCardPostion.x, self.BgCardPostion.y)
end

function P:initHandCards()
	if not self._BgCard then
		local cardNames = {
			{"views/table/PK/BgCard1", "views/table/PK/BgCard2"},
			{"views/table/PK/BgCardOmaha1", "views/table/PK/BgCardOmaha2"},
		}
		self._BgCard = bee.createObj(cardNames[self.data:isOmaha() and 2 or 1][self:isMe() and 1 or 2])
		self._BgCard.transform:SetParent(self.BgCard.transform, false)
	end
	bee.invoke(self._BgCard, "setData", self.data, self.seatid, self)
end

function P:refreshUI()
	local info = self.data:getPlayer(self.seatid)
	local skinData = tpl_character_skin[info.skin_id]
	if skinData then
		if self._skinData ~= skinData then
			self._skinData = skinData
			if self._roleSpine then
				CU.GameObject.Destroy(self._roleSpine)
				self._roleSpine = nil
				self._roleSpineNode = nil
			end
		end
		if skinData.table_avatar then
			if not self._roleSpine then
				self._roleSpine = bee.createObj(skinData.table_avatar)
				self._roleSpine.transform:SetParent(self.ImageRole.transform, false)
				self.ImageRole:GetComponent("Image").enabled = false
				if not self:isMe() then
					self._roleSpine.transform.localScale = Config.ROLE_OTHER_SCALE
				end
				
				local Mask = self:find("Mask", self._roleSpine)
				if Mask then
					if bee.isIos or bee.isEditor then
						bee.convertMaskToSoftMask(Mask)
					end
					self._roleMask = Mask
					self._roleMask2 = self:find("Mask2", self._roleSpine)
					if self._roleMask2 then
						self._roleMask2:GetComponent("Image").raycastTarget = false
					end
					self._roleSpineNode = Mask.transform:GetChild(0).gameObject
					self._roleSpinePos = self._roleSpineNode.transform.localPosition
					bee.invoke(self._roleSpineNode, "setHideAttachments", info.skin_id)
				end
			end

			if SettingModel:isScrapPlayer(self.data, info.uid) then
				bee.invoke(self._roleSpineNode, "setScrap", true)
			else
				bee.invoke(self._roleSpineNode, "setScrap", false)
			end
		else
			bee.setIcon(self.ImageRole, skinData.table_avatar_pic)
			self.ImageRole:GetComponent("Image").enabled = true
		end
	end
	P.super.refreshUI(self)
	GF.setTitleImage(self.ImageTitle, info.title, true, true)
	self:initHandCards()
	self:refreshPlayUI()
	-- if info.is_fold then
	-- 	self:foldCard()
	-- end
end

function P:refreshPlayUI(is_reset)
	self:refreshActionUI()
	self:refreshCard(is_reset)
	self:resetWinPotSpr()
	self:showWinNodes(false)
	self:showLoseNodes(false)
	self:refreshAllin()
	self:refreshAddingChips(true)
	self:refreshFold()
	bee.invoke(self._BgCard, "refreshWinRate")
end

function P:refreshActionUI(instant)
	local info = self.data:getPlayer(self.seatid)
	self:refreshBet(info, instant)
	local actionIndex = self.data:getActionIndex()
	if actionIndex == self.seatid and self.data:getLeftActionTime() + self.data:getThinkTime() > 0 then
		self:startProgress(self.data:getLeftActionTime())
	else
		self:stopProgress(true)
	end
	self:refreshFightFxUi()
end

function P:refreshEyes()
	bee.invoke(self._BgCard, "refreshEyes")
end

function P:refreshCard(is_reset)
	bee.invoke(self._BgCard, "refreshCard", is_reset)
end

function P:checkCards(info)
end

function P:_showBetAnim(info)
	local actionTag = POKER_ACTION_TAGS[info.action_type]
	self.in_hand_to_bet = true
	local tmp = CU.GameObject.Instantiate(self.BgBet, self.transform, false)
	self.tmp_nodes[#self.tmp_nodes + 1] = tmp
	-- tmp.transform.localPosition = bee.v3zero
	tmp.transform.localScale = Config.CARD_SCALE_BET
	tmp:SetActive(true)

	if actionTag and actionTag.nameImg then
		bee.setIcon(self:find("ImageTag", tmp), _I(actionTag.nameImg))
	end
	bee.setTextOrigin(self:find("TextBet", tmp), self.data:getBetChipsStr(info.bet_change))
	
	local dt = tpl_constdata.IngameBetDt
	local bet_chip = info.bet_chip
	local pos = self._seatNode._tableInfo:getPotPosition()
	bee.tween(tmp, true)
	: to(0.5, {scale = bee.v3one})
	: delay(0.5)
	: to(dt, {position = pos, scale = bee.v3(0.3, 0.3, 0.3)})
	: onComplete(function()
		CU.GameObject.Destroy(tmp)
		self.in_hand_to_bet = false
		if not self.in_bet_to_pot then
			self._seatNode._tableInfo:showPot(info.bet_chip)
		end
		if self.betToPotCB then
			--self.betToPotCB()
			self.betToPotCB = nil
		end
	end)
	: link()
end

function P:refreshBet(info, instant)
	self.in_hand_to_bet = false
	if info and info.bet_chip > 0 then
		if instant and info.bet_change > 0 then
			local actionTag = POKER_ACTION_TAGS[info.action_type]
			if actionTag and actionTag.nameImg then
				local dt = self.data:getAntiActionDt()
				self:refreshChip(info, 1 + tpl_constdata.IngameBetDt)
				if dt and dt > 0 then
					self:once(dt, function()
						self:_showBetAnim(info)
					end)
				else
					self:_showBetAnim(info)
				end
			elseif info.action_type == POKER_ACTION.ANTE then
				self:refreshChip(info)
				self._seatNode._tableInfo:showPot(info.bet_chip)
			else
				self:refreshChip(info)
				-- local from = self.TextChip.transform.position
				-- local to = self.tableLayer.ImagePot.transform.position
				-- self:flyChipsToPot(from, to, 5, function()
				-- end)
			end
		else
			if not self.data:getAntiActionDt() then
				self._seatNode._tableInfo:showPot(info.bet_chip)
				self._seatNode._tableInfo:showTag(info.action_type)
			end
		end
	elseif self.betToPotCB or self.in_bet_to_pot then
		if not self.data:getAntiActionDt() then
			self._seatNode._tableInfo:showTag(self.data:isPlaying() and info.action_type)
		end
	else
		self._seatNode._tableInfo:showPot()
		self._seatNode._tableInfo:showTag(self.data:isPlaying() and info.action_type)
		-- self.BgBet:SetActive(false)
	end
end

function P:showCard(visible, index, isBack)
	bee.invoke(self._BgCard, "showCard", visible, index, isBack)
end

function P:showCardForce()
	bee.invoke(self._BgCard, "showCardForce")
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
	bee.invoke(self._BgCard, "showCardAndFlop", isDealing)
end

function P:showCardStatus()
	bee.invoke(self._BgCard, "showCardStatus")
end

function P:showCardType(cardType, cards, isDealing, pkType)
	bee.invoke(self._BgCard, "showCardType", cardType, cards, isDealing, pkType)
end

function P:refreshWinRate()
	bee.invoke(self._BgCard, "refreshWinRate")
end

function P:foldCard()
	local info = self.data:getPlayer(self.seatid)
	if not info or 0 == info.uid then
		return
	end
	self:playScrap(function()
		if self:isMe() then
			bee.invoke(self._BgCard, "setCardGrep")
		else
			if self._roleSpineNode then
				bee.invoke(self._roleSpineNode, "pauseAnim", true)
			end
		end
		
		bee.Tween.killByTarget(self.BgFold)
		self.BgFold:SetActive(true)
		self.BgFold.transform.localScale = bee.v3zero
		self.BgFold.transform.localPosition = bee.v3(0, 120)
		LAN:refreshLan(self.BgFold, true)
		bee.tween(self.BgFold)
		: to(0.2, {scale = bee.v3one})
		: delay(0.2)
		: to(0.5, {scale = bee.v3(0.7, 0.7, 0.7), position = bee.v3(0, self:isMe() and 300 or 230)})
		: link()
		: setTarget()
	end)

	-- self:setCardGrep()
	-- self:showLoseNodes(true)
	-- self:recyclingCards()
end

function P:playSound(key)
	local info = self.data:getPlayer(self.seatid)
	if info then
		local d = tpl_character_skin[info.skin_id]
		if d then
			if key == ROLE_VOICE.all_in and d.kind == SKIN_KIND.AWAKEN then
				key = ROLE_VOICE.all_in_awakened
			end
			if type(key) == "table" then
				if self:isMe() then
					if not key["_myIndex"] then
						key["_myIndex"] = 1
					else
						key["_myIndex"] = key["_myIndex"] + 1
					end
					if key["_myIndex"] > #key then
						key["_myIndex"] = 1
					end
					Game:playRoleInVoice(d.role, key[key["_myIndex"]])
				else
					Game:playRoleInVoice(d.role, key[math.random(#key)])
				end
			else
				Game:playRoleInVoice(d.role, key)
			end
		end
	end
end

function P:playScrap(cb)
	self._isInScraping = true
	local info = self.data:getPlayer(self.seatid)
	if info then
		local isNeedScrap = info.chips <= 0
		if not isNeedScrap then
			if self.data:isSNG() then
				isNeedScrap = info.begin_chips - info.chips >= self.data.room_info.bust_threshold
			else
				isNeedScrap = info.begin_chips - info.chips >= self.data:getBigBlind() * tpl_constdata.ScrapBlindRate
			end
		end
		if isNeedScrap then
			SettingModel:setScrapPlayer(self.data, info.uid, true)
			if self._roleSpineNode then
				-- if not bee.invoke(self._roleSpineNode, "isInScrapState") then
				if true then
					bee.invoke(self._roleSpineNode, "playScrap")
					if info.chips > 0 or not (self.data:isSNG() or self.data:isMTT()) then
						self:once(0.2, function()
							self:playSound(ROLE_VOICE.scrap)
						end)
					end
					self._roleSpineNode.transform:SetParent(self._roleMask2.transform, true)
					local roleSpinePos = self._roleSpineNode.transform.localPosition
					if not info:isMe() then
						self.BgRole.transform.localScale = Config.ROLE_ACTION_SCALE
						bee.tween(self.BgRole)
						: to(0.2, {position = bee.v3(0, -100)})
						: link()
						bee.tween(self._roleSpineNode)
						: to(0.2, {position = bee.v3(roleSpinePos.x, roleSpinePos.y + 100, 0)})
						: link()
						-- self._roleSpineNode.transform.localPosition = bee.v3(roleSpinePos.x, roleSpinePos.y + 100, 0)
					else
						bee.tween(self._roleSpineNode)
						: to(0.2, {position = bee.v3(roleSpinePos.x, roleSpinePos.y + 150, 0)})
						: link()
						-- self._roleSpineNode.transform.localPosition = bee.v3(roleSpinePos.x, roleSpinePos.y + 150, 0)
					end
					self:once(2, function()
						self._isInScraping = false
						bee.tween(self.BgRole)
						: to(0.2, {position = bee.v3zero})
						: link()
						bee.tween(self._roleSpineNode)
						: to(0.2, {position = roleSpinePos})
						: onComplete(function()
							self._roleSpineNode.transform:SetParent(self._roleMask.transform, true)
						end)
						: link()
						if not info:isMe() then
							bee.tween(self.BgRole.transform)
							: to(0.2, {scale = bee.v3one})
						end
						bee.emit(self._roleSpineNode, "tryPlayIdle")
						if cb then cb() end
					end)
					return
				end
				if not info:isMe() then
					bee.invoke(self._roleSpineNode, "pauseAnim", true)
				end
			end
		end
	end
	self._isInScraping = false
	if cb then cb() end
end

function P:stopScrap()
	if self._roleSpineNode then
		bee.invoke(self._roleSpineNode, "resumeAnim", "idle")
	end
end

function P:playUnScrap()
	if self._roleSpineNode then
		bee.invoke(self._roleSpineNode, "stopScrap")
	end
end

function P:showWinNodes(flag)
	bee.invoke(self._BgCard, "showWinNodes", flag)
end

function P:showLoseNodes(flag)
	bee.invoke(self._BgCard, "showLoseNodes", flag)
end

function P:showOmahaWinHands()
	bee.invoke(self._BgCard, "showOmahaWinHands")
end

function P:refreshAllin()
	local player = self.data:getPlayer(self.seatid)
	if player:isAllin() then
		self:showAllin()
	else
		if not bee.isNull(self._allinEft) then
			GameModel.layer:putEffectItem(self._allinEft)
			self._allinEft = nil
		end
	end
end

function P:showAllin()
	if bee.isNull(self._allinEft) then
		local effId = self.data:getPlayer(self.seatid).nameplate_eff
		if self:isMe() then
			self._allinEft = GameModel.layer:playUIEffect(GameModel:getAllinEffectName(0, effId), self.BgAllin.transform, nil, -1)
		else
			self._allinEft = GameModel.layer:playUIEffect(GameModel:getAllinEffectName(1 + self.data:getPlayer(self.seatid).user_type, effId), self.BgAllin.transform, nil, -1)
		end
	end
end

function P:getCardWorldPos(index)
	return bee.invoke(self._BgCard, "getCardWorldPos", index)
end

-- 牌局结束后，回收手牌牌
function P:recyclingCards()
	bee.invoke(self._BgCard, "recyclingCards")
	
	self:refreshAllin()
end

function P:getCollectBetToPotDt()
	if self.in_hand_to_bet then
		return 0.3
	end
	return 0
end

function P:flyChipsToPot(from, to, num, cb)
	for i = 1, num do
		local eft = GameModel.layer:playUIEffect(self.data:getChipEft(), GameModel.layer.transform, nil, 3)
		eft.transform.position = from
		local pos = eft.transform.localPosition
		local ranPos = CU.Random.insideUnitCircle * 65
		bee.tween(eft)
		: to(0.066, {position = bee.v3(ranPos.x + pos.x, ranPos.y + pos.y)})
		: onComplete(function()
			bee.tween(eft, true)
			: to (0.533, {position = to})
			: ease(DT.Ease.InBack)
			: onComplete(function()
				GameModel.layer:putEffectItem(eft)
				if i == 1 then
					cb()
				end
			end)
			: link()
		end)
		: link()
	end
end

function P:collectBetToPot(collectDt)
	self.in_bet_to_pot = false
	local info = self.data:getPlayer(self.seatid)
	if info.bet_chip == 0 then
		return
	end
	self.in_bet_to_pot = true
	local function doCollect()
		if bee.isNull(self.node) or not GameModel.layer then
			return
		end
		local isFromBet = not self.data:isInAnte()
		self.BgBet:SetActive(false)

		local num = 5
		if info.bet_chip > self.data:getBigBlind() * 200 then
			num = 20
		elseif info.bet_chip >= self.data:getBigBlind() * 40 then
			num = 10
		end
		self._seatNode._tableInfo:hidePot()
		local from = isFromBet and self._seatNode._tableInfo.ImageBet.transform.position or self.TextChip.transform.position
		local to = self.tableLayer.ImagePot.transform.position

		self:flyChipsToPot(from, to, num, function()
			self.in_bet_to_pot = false
			if self.potToHandCB then
				self.potToHandCB()
				self.potToHandCB = nil
			end
		end)
	end
	if self.in_hand_to_bet then
		self.betToPotCB = doCollect
	end
	if collectDt > 0 then
		self:once(collectDt, doCollect)
	else
		doCollect()
	end
end

function P:collectPotToHand(chips, cb)
	local function doCollect()
		local num = 5
		if chips > self.data:getBigBlind() * 200 then
			num = 20
		elseif chips >= self.data:getBigBlind() * 40 then
			num = 10
		end

		if num == 5 then
			Game:playSound("ui_chips_win_1")
		elseif num == 10 then
			Game:playSound("ui_chips_win_2")
		else
			Game:playSound("ui_chips_win_3")
		end

		local info = self.data:getPlayer(self.seatid)
		local from = GameModel.layer:getBgPot().transform.position
		local to = self.TextChip.transform.position
		local center = GameModel.layer.ChipMids[self.info_index].transform.position

		local minDt, maxDt = 400, 600
		if self.info_index ~= 6 then
			minDt, maxDt = 533, 866
		end
		for i = 1, num do
			local eft = GameModel.layer:playUIEffect(self.data:getChipEft(), GameModel.layer.transform, nil, 3)
			eft.transform.position = from
			local pos = eft.transform.localPosition
			local ranPos = CU.Random.insideUnitCircle * 65
			bee.tween(eft)
			: to(0.066, {position = bee.v3(ranPos.x + pos.x, ranPos.y + pos.y)})
			: onComplete(function()
				local dt = minDt + (i - 1) * 30
				if dt > maxDt then
					dt = math.random(minDt, maxDt)
				end
				local cmp = CS.BezierAction.BezierTo(eft, eft.transform.position, center, to, dt/1000)
				cmp.isLocal = false
				cmp:OnComplete(function()
					if i == 1 then
						self:refreshChip(info, 0.2)
						local tip = GameModel.layer:playUIEffect("views/table/PK/IngameTipChip", self.transform, bee.v3(0, 200))
						if tip then
							bee.setTextOrigin(self:find("AnimRoot/TextAdd", tip), "+" .. self.data:getBetChipsStr(chips))
						end
						if cb then
							cb()
						end
					end
					GameModel.layer:putEffectItem(eft)
				end)
			end)
			: link()
		end
	end
	if self.in_bet_to_pot then
		self.potToHandCB = doCollect
	else
		doCollect()
	end
end

function P:cleanSeatCollectCB()
	self.potToHandCB = nil
end

function P:refreshSittingOut()
	-- 别删
end

function P:refreshAddingChips(is_adding, chips, type)
	if self.data:getRebuyRemainTime(self.seatid) > 0 then
		local data = GF.getTableDataBySB(self.data:getGameType(), self.data:getSmallBlind())
		if data then
			if self.data:isFriendsRoom() then
				UiManager:showUI("FriendsRoomByin")
			elseif (data.min_byin or data.byin) <= PlayerModel:getGold() then
				UiManager:showUI("LobbyByinDialog", {data = data, isReby = true})
			else
				if not UiManager:getUI("IngameQuickBy") then
					UiManager:showUI("IngameQuickBy", {data = data, dt = self.data:getRebuyRemainTime(self.seatid)})
				end
			end
		else
			printError("refreshAddingChips no table data for sb: " .. self.data:getSmallBlind())
		end
	end
end

function P:refreshFightFxUi()
	self:hideFightFx()
	local info = self.data:getPlayer(self.seatid)
	if info.chips == 0 and self.data:isPlayerPlaying(self.seatid) then
		self:showFightFx()
	end	
end

return P
