local P = class("PKActionLayer", UiBase)

local RAISE_STEP = {
	{max = 10, gap = 1},
	{max = 30, gap = 2},
	{max = 100, gap = 5},
	{max = 400, gap = 10},
	{max = 1000, gap = 20},
	{max = 5000, gap = 50},
}

local PRE_ACTION = {
	CHECK_FOLD = 1,
	CALL_CURRENT = 2,
	CALL_ANY = 3,
}

function P:setParams(params)
    P.super.setParams(self, params)
    self.data = params.data
end

function P:onAwake()
    self.ImageBg = self:find("ImageBg")
	self.BgAction = self:find("BgAction", self.ImageBg)
	self.BgActionPre = self:find("BgActionPre", self.ImageBg)

    self.FoldButton = self:find("FoldButton", self.BgAction)
    self.CheckButton = self:find("CheckButton", self.BgAction)
    self.BetButton = self:find("BetButton", self.BgAction)
    self.CallButton = self:find("CallButton", self.BgAction)
    self.RaiseButton = self:find("RaiseButton", self.BgAction)
	self.AllinCallButton = self:find("AllinCallButton", self.BgAction)

	self.BgRaise = self:find("Raise", self.BgAction)
	self.RaiseSlider = self:find("RaiseSlider", self.BgRaise)
	self.PlusButton = self:find("PlusButton", self.BgRaise)
	self.MinusButton = self:find("MinusButton", self.BgRaise)
	self.AllinButton = self:find("AllinButton", self.BgRaise)

	self.AllinEffect = self:find("Eff_PKtable_allin_fire", self.AllinCallButton)
	self.SliderEffect = self:find("Eff_PKtable_allin_jdt", self.RaiseSlider)
	if self.AllinEffect then
		self.AllinEffect:SetActive(false)
	end
	if self.SliderEffect then
		self.SliderEffect:SetActive(false)
	end

	self.BgPotPK = self:find("BgPotPK", self.BgRaise)
	self.PotButtons = {
		self:find("Pot1Button", self.BgPotPK),
		self:find("Pot2Button", self.BgPotPK),
		self:find("Pot3Button", self.BgPotPK),
		self:find("Pot4Button", self.BgPotPK),
	}

	self.BgBetPk = self:find("BgBetPk", self.BgRaise)
	self.BetPotButton = self:find("BetPotButton", self.BgBetPk)
	self.Bet3Button = self:find("Bet3Button", self.BgBetPk)
	self.Bet4Button = self:find("Bet4Button", self.BgBetPk)
	self.Bet5Button = self:find("Bet5Button", self.BgBetPk)

    self.TextBet = self:find("Text", self.BetButton)
    self.TextBetNum = self:find("TextNum", self.BetButton)
    self.ImageBet = self:find("Image", self.BetButton)
    self.TextCall = self:find("Text", self.CallButton)
    self.TextCallNum = self:find("TextNum", self.CallButton)
    self.TextRaise = self:find("Text", self.RaiseButton)
    self.TextRaiseNum = self:find("TextNum", self.RaiseButton)
    self.ImageRaise = self:find("Image", self.RaiseButton)
    self.TextAllinCall = self:find("Text", self.AllinCallButton)
    self.TextAllinCallNum = self:find("TextNum", self.AllinCallButton)

	self.ButtonCheckFold = self:find("ButtonCheckFold", self.BgActionPre)
	self.ButtonCallCurrent = self:find("ButtonCallCurrent", self.BgActionPre)
	self.ButtonCallAny = self:find("ButtonCallAny", self.BgActionPre)
	self.PreActions = {
		self.ButtonCheckFold,
		self.ButtonCallCurrent,
		self.ButtonCallAny,
	}


    bee.addClick(self.FoldButton, function()
    	Game:playSound("ui_button_confirm")
		if self.data:getCallNeedChip() <= 0 and self.data:getLeftActionTime() > 0 then
			self._foldDialog = UiManager:showTip({
				text = _T("LAB_GAME_046"),
				closeNoCancel = true,
				sureStr = _T("LAB_CHECK") .. "(" .. math.floor(self.data:getLeftActionTime()) .. ")",
				cancelStr = _T("LAB_FOLD"),
				onSure = function()
					Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.CHECK})
				end,
				onCancel = function()
					Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.FOLD})
				end
			})
			self._foldDialog:schedule(1, function()
				local dt = math.floor(self.data:getLeftActionTime())
				self._foldDialog:setSureText(_T("LAB_CHECK") .. "(" .. dt .. ")")
				if dt <= 0 then
					Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.CHECK})
					self._foldDialog:hideUI()
					self._foldDialog = nil
				end
			end)
		else
        	Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.FOLD})
		end
    end)
    bee.addClick(self.CheckButton, function()
    	Game:playSound("ui_button_confirm")
        Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.CHECK})
    end)
    bee.addClick(self.BetButton, function()
    	Game:playSound("ui_button_confirm")
		if self.__actBetDt == scheduler.timeSpend then return end
		self.__actBetDt = scheduler.timeSpend

		if not self.BgRaise.activeSelf and not self._isCanAllin then
			self._raiseType = POKER_ACTION.BET
			self:refreshBetList()
			self.ImageBet:SetActive(true)
		else
			self:_doBetAction(POKER_ACTION.BET, self._betValue)
		end
    end)
    bee.addClick(self.CallButton, function()
    	Game:playSound("ui_button_confirm")
        Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.CALL})
    end)
    bee.addClick(self.RaiseButton, function()
    	Game:playSound("ui_button_confirm")
		if self.__actRaiseDt == scheduler.timeSpend then return end
		self.__actRaiseDt = scheduler.timeSpend
		
		if not self.BgRaise.activeSelf and not self._isCanAllin then
			self._raiseType = POKER_ACTION.RAISE
			self:refreshBetList()
			self.ImageRaise:SetActive(true)
		else
			self:_doBetAction(POKER_ACTION.RAISE, self._betValue)
		end
    end)
	bee.addClick(self.AllinCallButton, function()
		Game:playSound("ui_button_confirm")
		Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.ALLIN})
	end)
    bee.addClick(self.AllinButton, function()
    	Game:playSound("ui_button_confirm")
		local my_info = self.data:getMyPlayerInfo()
		if SettingModel:isBetPrecise() and not GuideManager:isInGuide() then
			local my_info = self.data:getMyPlayerInfo()
			self:setBetValueWithChip(my_info.chips + my_info.bet_chip, true)
		else
        	Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.ALLIN, chips = my_info.chips})
		end
		-- self:setBetValueWithChip(my_info.chips, true)
		if self._raiseType == POKER_ACTION.BET then
        	bee.logEvent("ingame-bet-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), {d1 = -1})
		else
			bee.logEvent("ingame-raise-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), {d1 = -1})
		end
    end)

	for k, v in ipairs(self.PotButtons) do
		bee.addClick(v, function()
			Game:playSound("ui_button_confirm")
			local info = self.data:getMyPlayerInfo()
			local chips = info.chips
			local pot = self.data:getTotalPot()
			if self._raiseType == POKER_ACTION.BET then
				local steps = SettingModel:getBetStep(self.data:isOmaha())
				local val = steps[SettingModel:getBetPkValues(self.data:getGameType(), true)[k]]
				if val[2] then
					pot = math.round(pot * val[1] / val[2])
				else
					pot = math.round(pot * val[1])
				end
				bee.logEvent("ingame-bet-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), {d1 = val[1] / (val[2] or 1)})
			else
				if SettingModel:getRaiseKind(nil, self.data:getGameType()) ~= 1 then
					pot = self.data:getRaiseBase()
				end
				local steps = SettingModel:getRaiseStep(self.data:isOmaha(), SettingModel:getRaiseKind(nil, self.data:getGameType()))
				local val = steps[SettingModel:getRaisePkValues(self.data:getGameType(), true, SettingModel:getRaiseKind(nil, self.data:getGameType()))[k]]
				local d1 = val
				if type(val) == "table" then
					if val[2] then
						pot = math.round(pot * val[1] / val[2])
					else
						pot = math.round(pot * val[1])
					end
					d1 = val[1] / (val[2] or 1)
				else
					pot = math.round(pot * val)
				end
				if self._raiseType == POKER_ACTION.RAISE and SettingModel:getRaiseKind(nil, self.data:getGameType()) == 1 then
					pot = pot + info.bet_chip
				end
				if 4 == k and self.data:isOmaha() then
					local totalPot = self.data:getTotalPot() + info.bet_chip
					if pot > totalPot then
						pot = totalPot
					end
				end
				bee.logEvent("ingame-raise-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), {d1 = d1})
			end
			
			if chips > pot then
				chips = pot
			end
			if SettingModel:isBetPrecise() and not GuideManager:isInGuide() then
				self:setBetValueWithChip(chips, true)
			else
				self:_doBetAction(self._raiseType, chips)
			end
		end)
	end
	
	bee.addClick(self.BetPotButton, function()
		Game:playSound("ui_button_confirm")
		local chips = self.data:getMyPlayerInfo().chips
		local pot = self.data:getTotalPot()
		if chips > pot then
			chips = pot
		end
		self:_doBetAction(self._raiseType, chips + self.data:getMyPlayerInfo().bet_chip)
	end)
	bee.addClick(self.Bet3Button, function()
		Game:playSound("ui_button_confirm")
		self:_doBetAction(self._raiseType, 3 * self.data:getBigBlind())
	end)
	bee.addClick(self.Bet4Button, function()
		Game:playSound("ui_button_confirm")
		self:_doBetAction(self._raiseType, 4 * self.data:getBigBlind())
	end)
	bee.addClick(self.Bet5Button, function()
		Game:playSound("ui_button_confirm")
		self:_doBetAction(self._raiseType, 5 * self.data:getBigBlind())
	end)

    bee.addClick(self.PlusButton, function()
    	Game:playSound("ui_button_confirm")
		if self._betIndex and #self._betList > 0 and self._betValue < self._betList[#self._betList] then
			-- self:setBetValueWithIndex(self._betIndex + 1, true)
			local chips = self._betValue + self.data:getBigBlind() / 10
			if chips > self._betList[#self._betList] then
				chips = self._betList[#self._betList]
			end
			self:setBetValueWithChip(chips, true)
		end
    end)
    bee.addClick(self.MinusButton, function()
    	Game:playSound("ui_button_confirm")
		if self._betIndex and #self._betList > 0 and self._betValue > self._betList[1] then
			-- self:setBetValueWithIndex(self._betIndex - 1, true)
			local chips = self._betValue - self.data:getBigBlind() / 10
			if chips < self._betList[1] then
				chips = self._betList[1]
			end
			self:setBetValueWithChip(chips, true)
		end
    end)

	self.BlindSlider = UiSliderEx:create(self.RaiseSlider)
    self.BlindSlider:onValueChanged(function(val)
    	Game:playSound("ui_button_confirm")
		if self._isSetValue then
			return
		end
    	self:setBetValueWithChip(val)
		Game:playSound("slider")
    end)

    bee.addClick(self.ButtonCheckFold, function()
    	Game:playSound("ui_button_confirm")
		-- self:setPreActionCheck(PRE_ACTION.CHECK_FOLD)
		if self._preAction == PRE_ACTION.CHECK_FOLD then
			Net:sendReq("pb.PreActionREQ", {type = 0, chips = 0})
		else
			Net:sendReq("pb.PreActionREQ", {type = PRE_ACTION.CHECK_FOLD, chips = 0})
        	bee.logEvent("ingame-pre-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), 1)
		end
    end)
    bee.addClick(self.ButtonCallCurrent, function()
    	Game:playSound("ui_button_confirm")
		-- self:setPreActionCheck(PRE_ACTION.CALL_CURRENT)
		if self._preAction == PRE_ACTION.CALL_CURRENT then
			Net:sendReq("pb.PreActionREQ", {type = 0, chips = 0})
		else
			Net:sendReq("pb.PreActionREQ", {type = PRE_ACTION.CALL_CURRENT, chips = self.data:getAutoCallChip()})
        	bee.logEvent("ingame-pre-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), 2)
		end
    end)
    bee.addClick(self.ButtonCallAny, function()
    	Game:playSound("ui_button_confirm")
		-- self:setPreActionCheck(PRE_ACTION.CALL_ANY)
		if self._preAction == PRE_ACTION.CALL_ANY then
			Net:sendReq("pb.PreActionREQ", {type = 0, chips = 0})
		else
			Net:sendReq("pb.PreActionREQ", {type = PRE_ACTION.CALL_ANY, chips = 0})
        	bee.logEvent("ingame-pre-btn", GameModel.data:getGameType(), GameModel.data:getRoomId(), 3)
		end
    end)
end

function P:onShow()
	P.super.onShow(self)
	
	local chipIcon = GameModel.data:getChipIcon()
	if chipIcon then
		bee.setIcon(self:find("Image/ingame_pot_chip", self.CallButton), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.BetButton), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.RaiseButton), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.AllinCallButton), chipIcon)

		bee.setIcon(self:find("Image/ingame_pot_chip", self.AllinButton), chipIcon)

		for _, v in ipairs(self.PotButtons) do
			bee.setIcon(self:find("Image/ingame_pot_chip", v), chipIcon)
		end
		
		bee.setIcon(self:find("Image/ingame_pot_chip", self.Bet3Button), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.Bet4Button), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.Bet5Button), chipIcon)
		bee.setIcon(self:find("Image/ingame_pot_chip", self.BetPotButton), chipIcon)
	end
end

function P:refreshUI()
	self.BgPotPK:SetActive(true)
	self.BgBetPk:SetActive(false)

	self:hideFoldDialog()

	if self.data:isMeOnSeat() and self.data:isMePlaying() and not self.data:isMeSittingOut() and not self.data:isMeFold() and not self.data:isMeSittingOut() then
		self.BgRaise:SetActive(false)
		if self.data:getActionIndex() == self.data:getMyPosition() then
			self:refreshContent()
		elseif self.data:getActionIndex() > 0 then
			self:hide(true, true)
			self:refreshAutoBnts(true)
		else
			self:hide(true, true)
		end
	else
		self:hide(true, true)
	end
end

function P:show(fast)
    self.ImageBg:SetActive(true)
end

function P:hide(fast, force)
    self.ImageBg:SetActive(false)
end

function P:hideFoldDialog()
	if self._foldDialog then
		self._foldDialog:hideUIForce()
		self._foldDialog = nil
	end
end

function P:refreshContent(fast)
	self:show(fast)
	self:showAutoBnts(false)
	self:showActionBnts(true)
	local max_bet_value = self.data:getMaxBetValue()
	local my_chip = self.data:getMyPlayerInfo().chips
	local call_need_chip = self.data:getCallNeedChip()
	local min_chip_in = self.data:getMinChipIn()
	local max_chip_in = self.data:getMyMaxChipIn()
	local can_check = call_need_chip == 0
	local can_call = call_need_chip > 0
	local can_bet = max_bet_value == 0
	local can_raise = not can_bet and min_chip_in > call_need_chip and my_chip > call_need_chip and max_chip_in > call_need_chip
	self.CheckButton:SetActive(can_check)
	self.CallButton:SetActive(can_call)
	self.BetButton:SetActive(can_bet)
	self.RaiseButton:SetActive(can_raise)
	self.AllinCallButton:SetActive(false)
	if can_call then
		local chip = math.min(my_chip, call_need_chip)
		if my_chip <= call_need_chip then
			self.AllinCallButton:SetActive(true)
			self.CallButton:SetActive(false)
			bee.setText(self.TextAllinCallNum, self.data:getBetChipsStr(chip))
		else
			bee.setText(self.TextCallNum, self.data:getBetChipsStr(chip))
		end
	end
	self._isCanAllin = false
	if self.AllinEffect then
		self.AllinEffect:SetActive(false)
	end
	if can_bet then
		local lab
		if my_chip <= self.data:getBigBlind() then
			self.AllinCallButton:SetActive(true)
			self.BetButton:SetActive(false)
			bee.setText(self.TextAllinCallNum, self.data:getBetChipsStr(my_chip))
		else
			lab = "LAB_BET"
			bee.setText(self.TextBetNum, "")
			self.ImageBet:SetActive(false)
		end
		bee.setText(self.TextBet, _T(lab))
	end
	if can_raise then
		local lab
		if my_chip <= min_chip_in then
			self.AllinCallButton:SetActive(true)
			self.RaiseButton:SetActive(false)
			bee.setText(self.TextAllinCallNum, self.data:getBetChipsStr(my_chip))
		else
			lab = "LAB_RAISE"
			bee.setText(self.TextRaiseNum, "")
			self.ImageRaise:SetActive(false)
		end
		bee.setText(self.TextRaise, _T(lab))
	end
	if can_bet or can_raise then
		self.BgRaise:SetActive(false)
	else
		self.BgRaise:SetActive(false)
	end
end

function P:refreshAutoBnts(fast)
	if not SettingModel:isPreAction() or GuideManager:isInGuide() then
		return
	end

	if self.data:getRoundStage() == POKER_ROUND.OVER then return end
	if not self.data:isMePlaying() or self.data:isMeFold() or self.data:isMeAllin() or self.data:isMeSittingOut() then return end

	self:showActionBnts(false)
	self:showAutoBnts(true)
	self:evt_PreActionRSP()
	self:show(fast)
end

function P:showAutoBnts(is_show)
	self.BgActionPre:SetActive(is_show and true or false)
end

function P:showActionBnts(is_show)
	self.BgAction:SetActive(is_show and true or false)
end

function P:setBetValueWithChip(chips, refreshSlider)
	for k, v in ipairs(self._betList) do
		if v >= chips then
			local idx = k
			if v > chips then
				if idx > 1 and math.abs(chips - v) > math.abs(chips - self._betList[idx - 1]) then
					idx = idx - 1
				end
			end
			self:setBetValueWithIndex(idx, refreshSlider)
			if self._betValue ~= chips then
				self._betValue = chips
				self:refreshBetValue()
			end
			local info = self.data:getMyPlayerInfo()
			if chips - info.bet_chip >= info.chips then
				self.AllinCallButton:SetActive(true)
				bee.setText(self.TextAllinCallNum, self.data:getBetChipsStr(chips))
				self.BetButton:SetActive(false)
				self.RaiseButton:SetActive(false)
				if self.AllinEffect then
					self.AllinEffect:SetActive(true)
				end
				if self.SliderEffect then
					self.SliderEffect:SetActive(true)
				end
			else
				self.AllinCallButton:SetActive(false)
				self.BetButton:SetActive(self._raiseType == POKER_ACTION.BET)
				self.RaiseButton:SetActive(self._raiseType == POKER_ACTION.RAISE)
				
				if self.AllinEffect then
					self.AllinEffect:SetActive(false)
				end
				if self.SliderEffect then
					self.SliderEffect:SetActive(false)
				end
			end
			break
		end
	end
end

function P:setBetValueWithIndex(index, refreshSlider)
	self._betIndex = index
	self._betValue = self._betList[index]
	self:refreshBetValue()

	if refreshSlider then
		self._isSetValue = true
		self.BlindSlider:setCurStep(index)
		self._isSetValue = false
	end
end

function P:refreshBetValue()
	local info = self.data:getMyPlayerInfo()
	bee.setText(self.TextBetNum, self.data:getBetChipsStr(self._betValue))
	bee.setText(self.TextRaiseNum, self.data:getBetChipsStr(self._betValue))
end

function P:refreshBetList()
	if self.SliderEffect then
		self.SliderEffect:SetActive(false)
	end
	self.BgRaise:SetActive(true)

	local my_info = self.data:getMyPlayerInfo()
	local min_chip_in, max_chip_in = self.data:getMinChipIn(), self.data:getMyMaxChipIn()
	local bb = self.data:getSmallBlind()
	local gapBB = bb
	local list = {}

	while min_chip_in <= max_chip_in do
		list[#list + 1] = min_chip_in + my_info.bet_chip
		min_chip_in = min_chip_in + gapBB
	end
	if list[#list] ~= max_chip_in + my_info.bet_chip then
		list[#list + 1] = max_chip_in + my_info.bet_chip
	end

	self._betList = list
	self.BlindSlider:setStepDatas(self._betList)
	self:setBetValueWithIndex(1, true)

	self:showFastPotButton(list)
end

function P:showFastBetButton(min_chip_in, max_chip_in, list)
	self.BgBetPk:SetActive(true)
	self.BgPotPK:SetActive(false)

	local my_info = self.data:getMyPlayerInfo()
	local pot = self.data:getTotalPot()
	local isOmaha = self.data:isOmaha()
	local b3, b4, b5 = 3 * self.data:getBigBlind(), 4 * self.data:getBigBlind(), 5 * self.data:getBigBlind()
	self.Bet3Button:SetActive(b3 - my_info.bet_chip <= my_info.chips and (not isOmaha or b3 - my_info.bet_chip <= pot))
	self.Bet4Button:SetActive(b4 - my_info.bet_chip <= my_info.chips and (not isOmaha or b4 - my_info.bet_chip <= pot))
	self.Bet5Button:SetActive(b5 - my_info.bet_chip <= my_info.chips and (not isOmaha or b5 - my_info.bet_chip <= pot))
	bee.setText(self:find("TextNum", self.Bet3Button), self.data:getBetChipsStr(b3))
	bee.setText(self:find("TextNum", self.Bet4Button), self.data:getBetChipsStr(b4))
	bee.setText(self:find("TextNum", self.Bet5Button), self.data:getBetChipsStr(b5))

	if isOmaha then
		if my_info.chips <= pot then
			self.AllinButton:SetActive(true)
			self:refreshAllinNum()
		else
			self.BetPotButton:SetActive(true)
			bee.setText(self:find("TextNum", self.BetPotButton), self.data:getBetChipsStr(pot + my_info.bet_chip))
			self.AllinButton:SetActive(false)
		end
		if not self.Bet3Button.activeSelf then
			self:showFastPotButton(list)
		end
	else
		self.BetPotButton:SetActive(false)
		self.AllinButton:SetActive(true)
		self:refreshAllinNum()
	end
end

function P:showFastPotButton(list)
	self.BgBetPk:SetActive(false)
	self.BgPotPK:SetActive(true)
	
	local bet_steps = SettingModel:getBetStep(self.data:isOmaha())
	local raise_steps = SettingModel:getRaiseStep(self.data:isOmaha(), SettingModel:getRaiseKind(nil, self.data:getGameType()))
	local info = self.data:getMyPlayerInfo()
	local min_chip_in, max_chip_in = self.data:getMinChipIn(), self.data:getMyMaxChipIn()
	local chips, bet_chip = info.chips, info.bet_chip
	local pot = self.data:getTotalPot()
	if self._raiseType == POKER_ACTION.RAISE and SettingModel:getRaiseKind(nil, self.data:getGameType()) ~= 1 then
		pot = self.data:getRaiseBase()
	end
	for k, v in ipairs(self.PotButtons) do
		local bet = pot
		if self._raiseType == POKER_ACTION.BET then
			local val = bet_steps[SettingModel:getBetPkValues(self.data:getGameType(), true)[k]]
			local valStr = GF.getBetNameStr(val)
			bee.setText(self:find("TextPot", v), valStr)
			if val[2] then
				bet = math.round(pot * val[1] / val[2])
			else
				bet = math.round(pot * val[1])
			end
			bee.setText(self:find("TextNum", v), self.data:getBetChipsStr(bet))
		else
			local val = raise_steps[SettingModel:getRaisePkValues(self.data:getGameType(), true, SettingModel:getRaiseKind(nil, self.data:getGameType()))[k]]
			local valStr = GF.getRaiseNameStr(val)
			bee.setText(self:find("TextPot", v), valStr)
			if type(val) == "table" then
				if val[2] then
					bet = math.round(pot * val[1] / val[2])
				else
					bet = math.round(pot * val[1])
				end
			else
				bet = math.round(pot * val)
			end
			if self._raiseType == POKER_ACTION.RAISE and SettingModel:getRaiseKind(nil, self.data:getGameType()) == 1 then
				bet = bet + bet_chip
			end
			bee.setText(self:find("TextNum", v), self.data:getBetChipsStr(bet))
		end
		bet = bet - bet_chip
		v:SetActive(bet > 0 and chips >= bet and bet >= list[1] - bet_chip and bet <= max_chip_in)
	end
	if self.data:isOmaha() then
		local totalPot = self.data:getTotalPot()
		if info.chips <= totalPot then
			self.AllinButton:SetActive(true)
			self.PotButtons[4]:SetActive(false)
		else
			self.AllinButton:SetActive(false)
			if not self.PotButtons[4].activeSelf then
				self.PotButtons[4]:SetActive(true)
				bee.setText(self:find("TextNum", self.PotButtons[4]), self.data:getBetChipsStr(totalPot + info.bet_chip))
				bee.setText(self:find("TextPot", self.PotButtons[4]), _F("LAB_GAME_016", ""))
			end
		end
	else
		self.AllinButton:SetActive(not self.PotButtons[4].activeSelf)
	end
	self:refreshAllinNum()
end

function P:refreshAllinNum()
	local info = self.data:getMyPlayerInfo()
	bee.setText(self:find("TextNum", self.AllinButton), self.data:getBetChipsStr(info.chips + info.bet_chip))
end

function P:refreshPreAction(isShow)
	if isShow then
		self.BgActionPre:SetActive(true)
		self.BgAction:SetActive(false)
		self:setPreActionCheck(nil)
	else
		self.BgActionPre:SetActive(false)
		self._preAction = nil
	end
end

function P:setPreActionCheck(act)
	self._preAction = act
	for k, v in pairs(self.PreActions) do
		if k == act then
			bee.setIcon(self:find("Image", v), "InGame[ingame_button_bg_01]")
			self:find("Text1", v):SetActive(false)
			self:find("Text2", v):SetActive(true)
		else
			bee.setIcon(self:find("Image", v), "InGame[ingame_button_bg_04]")
			self:find("Text1", v):SetActive(true)
			self:find("Text2", v):SetActive(false)
		end
	end
end

function P:_doBetAction(actionType, chips)
	chips = chips - self.data:getMyPlayerInfo().bet_chip
	if chips >= self.data:getMyPlayerInfo().chips then
		Net:sendReq("pb.ActionREQ", {action_type = POKER_ACTION.ALLIN, chips = chips})
	else
		actionType = actionType or POKER_ACTION.RAISE
		Net:sendReq("pb.ActionREQ", {action_type = actionType, chips = chips})
	end
end

function P:evt_TableGameOverRSP()
	self:hide(true)
end

function P:evt_ActionNotifyBRC(msg)
	self:hide(true)	
	local index = self.data:getActionIndex()
	if index == self.data:getMyPosition() and self.data:getMyPlayerInfo() then
		local pre_action_result = msg and msg.pre_action_result or 0
		if pre_action_result == 2 then
			self:showAutoBnts(false)
			self:showActionBnts(false)
			self.data:setLeftActionTime(0)
		else
			if self.data:isMeSittingOut() then
				self:hide(true, true)
			else
				self:refreshContent()
			end
		end
		self.data:setPreActionDatas(0, 0)
	elseif index ~= self.data:getMyPosition() then
		self:refreshAutoBnts(nil)
	end
end

function P:evt_ActionBRC(msg)
	local seatid = msg.seatid + 1
	local myPosition = self.data:getMyPosition()
	local fast = myPosition == seatid and msg.action_type ~= POKER_ACTION.SB and msg.action_type ~= POKER_ACTION.BB
	local actionIndex = self.data:getActionIndex()
	if actionIndex == 0 then
		if myPosition == seatid then
			self:hide(fast)
		end
	end
	self:hideFoldDialog()
end

function P:evt_WinnerRSP()
	self:hide()
	self:setUnSelectCbox()
	self.data:setPreActionDatas(0, 0)
	self:hideFoldDialog()
end

function P:evt_RoundStartBRC()
	self:hide()
	self:setUnSelectCbox()
	self.data:setPreActionDatas(0, 0)
end

function P:evt_ShowHandRSP()
	self:hide()
	self:setUnSelectCbox()
	self.data:setPreActionDatas(0, 0)
end

function P:evt_PreActionRSP()
	local datas = self.data:getPreActionDatas()
	if datas and datas.pre_action_type and datas.pre_action_chips then
		self:setPreActionCheck(datas.pre_action_type)
	else
		self:setPreActionCheck(nil)
	end
end

function P:evt_PreActionResetRSP()
	-- self:setUnSelectCbox()
	self:setPreActionCheck(nil)
end

function P:evt_refreshShowBB()
	self:refreshUI()
end

function P:evt_GetRoomDataRSP(msg)
	self:refreshUI()
end

function P:evt_ReserveSeatRSP(msg)
	self:refreshUI()
end

function P:evt_SeatStatusBRC(msg)
	local seatid = msg.seatid + 1
	if seatid == self.data:getMyPosition() then
		self:refreshUI()
	end
end

function P:setUnSelectCbox()
end

return P