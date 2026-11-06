local P = class("SoccerBet", UiFullView)

function P:onAwake()
	local Pannel = self:find("AnimRoot/Center/Panel")
	self.CloseButton = self:find("CloseButton", Pannel)

	self.EmptyCont = self:find("EmptyCont", Pannel)
	self.GoBetButton = self:find("GoBetButton", self.EmptyCont)

	self.SoccerBetList = self:find("SoccerBetList", Pannel)
	self.Item1 = self:find("Item1", self.SoccerBetList)
	self.Item2 = self:find("Item2", self.SoccerBetList)
	self.Item1:SetActive(false)
	self.Item2:SetActive(false)

	self.vertime = 1787155200

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self:find("AnimRoot/common_panel_mask_70"), function()
		self:hideUI()
	end)

	bee.addClick(self.GoBetButton, function()
		Game:playSound("ui_button_confirm")
		local betId
		for i,v in ipairs(SoccerGuessingModel:getSoccerList()) do
			if v.status == 0 and v.lock ~= 1 then
				betId = v.bet_id
				break
			end
		end
		if not UiManager:getUI("SoccerMain") then
			UiManager:showUI("SoccerMain", {jumpId = betId})
		elseif self._params and self._params.goCb then
			self._params.goCb(betId)
		end
		self:hideUI()
	end)
end

function P:onStart()
	self:initBetList()
	SoccerGuessingModel:reqBetHistory()
end

function P:initBetList()
	self.betList = UiListEx:create(self.SoccerBetList)
	self.betList:setCreateFunc(function(data)
		if data.__kind == 1 then
			return CU.GameObject.Instantiate(self.Item1)
		else
			return CU.GameObject.Instantiate(self.Item2)
		end
	end)
	self.betList:setRefreshFunc(function(data, item)
		if data.__kind == 1 then
			self:setItemDetail(item, data)
		else
			self:setItem(item, data)
		end
	end)
	self.betList:setWidth({[1] = 452, [2] = 85})
end

function P:evt_BetHistoryListUpdate()
	self._data = SoccerGuessingModel:getSoccerHistoryList()
	if not self._data or not next(self._data) then
		self.EmptyCont:SetActive(true)
		self.SoccerBetList:SetActive(false)
		self.GoBetButton:SetActive(SoccerGuessingModel:getIsCanBet())
		return
	end

	self.EmptyCont:SetActive(false)
	self.SoccerBetList:SetActive(true)

	for i, v in ipairs(self._data) do
		if i == 1 then
			v.__kind = 1
		else
			v.__kind = 2
		end
	end
	self.betList:setDatas(self._data)
end

function P:setItemDetail(item, data)
	local TitleBg = self:find("TitleBg", item)
	local Title = self:find("Title", TitleBg)
	local Left = self:find("BetCont/Left", item)
	local Draw = self:find("BetCont/Draw", item)
	local Right = self:find("BetCont/Right", item)
	local GoButton = self:find("GoButton", item)
	local RewardText = self:find("RewardText", item)

	local betArea = {}
	for k,v in pairs(data.bet_area) do
		betArea[v.type] = v
	end
	local timeStr = os.date("%Y".."/".."%m".."/".."%d %H"..":".."%M", data.game_start_time)
	self:_setTitleText(Title, _F("LAB_FOOTBALL_12", timeStr, betArea[1].name, betArea[2].name, self:_getStatusText(data)))

	-- if data.bet_type == 1 then
	-- 	Draw:SetActive(true)
	-- 	self:_setBetItem(Draw, betArea[3])
	-- else
	-- 	Draw:SetActive(false)
	-- end
	bee.setText(self:find("NameText", Left), betArea[1].name)
	bee.setText(self:find("NameText", Right), betArea[2].name)
	self:_setBetItem(Left, betArea[1])
	self:_setBetItem(Right, betArea[2])
	self:_setBetItem(Draw, betArea[3])

	if data.status == 0 then
		if SoccerGuessingModel:getSoccerIsCanBet(data.bet_id) then
			GoButton:SetActive(true)
			RewardText:SetActive(false)
		else
			GoButton:SetActive(false)
			RewardText:SetActive(true)
			bee.setText(RewardText, _T("LAB_FOOTBALL_16"))
		end
	elseif data.status == 1 then
		GoButton:SetActive(false)
		RewardText:SetActive(true)
		bee.setText(RewardText, _T("LAB_FOOTBALL_16"))
	elseif data.status == 2 then
		GoButton:SetActive(false)
		RewardText:SetActive(true)
		bee.setText(RewardText, _T("LAB_FOOTBALL_17"))
	end

	bee.removeAllClick(TitleBg)
	bee.addClick(TitleBg, function()
		Game:playSound("ui_button_confirm")
		data.__kind = 2
		self.betList:clear()
		self.betList:setDatas(self._data)
	end)

	bee.removeAllClick(GoButton)
	bee.addClick(GoButton, function()
		Game:playSound("ui_button_confirm")
		if not UiManager:getUI("SoccerMain") then
			UiManager:showUI("SoccerMain", {jumpId = data.bet_id})
		elseif self._params and self._params.goCb then
			self._params.goCb(data.bet_id)
		end
		self:hideUI()
	end)
end

function P:_setTitleText(titleItem, textCont)
	local TitleText = self:find("TitleText", titleItem)
	bee.setText(TitleText, textCont)

    local s = titleItem.transform.sizeDelta
    local len = CS.Utils.GetTextWidth(TitleText:GetComponent("Text"), textCont)
    bee.Tween.killByTarget(TitleText)
    if len <= s.x then
        TitleText.transform.localPosition = bee.v3zero
    else
        local offset = (len - s.x) / 2
		local offset2 = offset * 2 + 25
        TitleText.transform.localPosition = bee.v3(offset)
        bee.tween(TitleText)
        : to(5, {position = bee.v3(-offset2, 0, 0)})
        : delay(3)
        : to(0, {position = bee.v3(offset, 0, 0)})
        : loop(-1)
        : link()
        : setTarget()
    end
end

function P:_setBetItem(item, betArea)
	local MineCount = self:find("MineCount", item)
	local RewardCount = self:find("RewardCount", item)
	if betArea and betArea.amount > 0 then
		bee.setText(MineCount, _N2(betArea.amount))
		self:find("Icon", MineCount):SetActive(true)
	else
		bee.setText(MineCount, "-")
		self:find("Icon", MineCount):SetActive(false)
	end
	if betArea and betArea.reward > 0 then
		bee.setText(RewardCount, _N2(betArea.reward))
		self:find("Icon", RewardCount):SetActive(true)
	else
		bee.setText(RewardCount, "-")
		self:find("Icon", RewardCount):SetActive(false)
	end
end

function P:setItem(item, data)
	local TitleBg = self:find("TitleBg", item)
	local Title = self:find("Title", TitleBg)

	local betArea = {}
	for k,v in pairs(data.bet_area) do
		betArea[v.type] = v
	end
	local timeStr = os.date("%Y".."/".."%m".."/".."%d %H"..":".."%M", data.game_start_time)
	self:_setTitleText(Title, _F("LAB_FOOTBALL_12", timeStr, betArea[1].name, betArea[2].name, self:_getStatusText(data)))

	bee.removeAllClick(TitleBg)
	bee.addClick(TitleBg, function()
		Game:playSound("ui_button_confirm")
		data.__kind = 1
		self.betList:clear()
		self.betList:setDatas(self._data)
	end)
end

function P:_getStatusText(data)
	if data.status == 0 then
		return _T("LAB_FOOTBALL_1")
	elseif data.status == 1 then
		if data.is_settled == 1 then
			if data.game_start_time < self.vertime then
				return _T("LAB_FOOTBALL_3")
			else
				return _T("LAB_FOOTBALL_3") .. (data.bet_area[1].regular_score or 0) ..":" .. (data.bet_area[2].regular_score or 0)
			end
		else
			return _T("LAB_FOOTBALL_TIPS_9")
		end
	elseif data.status == 2 then
		return _T("LAB_FOOTBALL_21")
	end
end

return P