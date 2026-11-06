local P = class("SoccerMain", UiFullView)

local SoccerStatus = {
	Normal = 0,		-- 正常（未开始、进行中）
	End = 1,		-- 已结束
	Removed = 2,	-- 下架
}
-- 竞赛类型
local BetType = {
	TeamWinner = 0,	-- 胜负
	Draw = 1,		-- 1X2胜平负
}
-- 下注区域
local AreaType = {
	Team1 = 1, 	-- 左边
	Team2 = 2,	-- 右边
	Draw = 3,	-- 平局
}
-- 比赛阶段
local MatchPeriod = {
	NotStart = 0,
	FirstHalf = 1,
	SecondHalf = 2,
	ExtraTime = 3,
	HalfTime = 4,
}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")

	local Pannel = self:find("Center/pannel", AnimRoot)
	self.Empty = self:find("Empty", Pannel)
	self.Main = self:find("Main", Pannel)

	local Score = self:find("Score", self.Main)
	self.TimeText = self:find("TimeText", Score)
	self.TimeStatus1 = self:find("TimeStatus1", Score)
	self.TimeStatus2 = self:find("TimeStatus2", Score)
	self.NewTag = self:find("NewTag", Score)
	self.nameContList = {}
	for i = 1, 3 do
		self.nameContList[i] = self:find("NameCont" .. i, Score)
	end

	self.Slider = self:find("Slider", self.Main)
	self.RightSlider = self:find("RightSlider", self.Slider)
	self.DrawSlider = self:find("DrawSlider", self.Slider)
	self.LeftSlider = self:find("LeftSlider", self.Slider)

	local BetPool = self:find("BetPool", self.Main)
	self.BetCont1 = self:find("BetCont1", BetPool)
	self.BetCont2 = self:find("BetCont2", BetPool)
	local Chip = self:find("Chip", BetPool)
	self.chipList = {}
	for i = 1, 4 do
		self.chipList[i] = self:find("Chip" .. i, Chip)
	end

	self.Lock = self:find("Lock", self.Main)
	self.ButtonCont = self:find("ButtonCont", self.Main)
	self.BetButton = self:find("BetButton", self.ButtonCont)
	self.DeleteButton = self:find("DeleteButton", self.ButtonCont)
	self.DetailButton = self:find("DetailButton", self.ButtonCont)
	self.EmptyImg = self:find("EmptyImg", self.ButtonCont)

	self.BetTipsPos = self:find("BetTipsPos", Pannel)
	self.BetTips = self:find("BetTips", self.BetTipsPos)
	self.TipsMask = self:find("TipsMask", self.BetTipsPos)
	self.TipsLeft = self:find("Table/TipsLeft", self.BetTips)
	self.TipsDraw = self:find("Table/TipsDraw", self.BetTips)
	self.TipsRight = self:find("Table/TipsRight", self.BetTips)
	self.BetTipsPos:SetActive(false)

	self.Switch = self:find("Switch", Pannel)
	self.ArrowLeft = self:find("ArrowLeft", self.Switch)
	self.ArrowRight = self:find("ArrowRight", self.Switch)
	self.ArrowLeft:SetActive(false)
	self.ArrowRight:SetActive(false)

	self.Page = self:find("Page", Pannel)
	self.Dot = self:find("Dot", self.Page)
	self.Dot:SetActive(false)

	local RightTop = self:find("RightTop", AnimRoot)
	self.GoldItem = self:find("GoldItem", RightTop)

	local LeftTop = self:find("LeftTop", AnimRoot)
	self.MyBetButton = self:find("MyBetButton", LeftTop)
	self.InfoButton = self:find("InfoButton", LeftTop)
	self.BackButton = self:find("BackButton", LeftTop)
	self.ReGuideButton = self:find("ReGuideButton", LeftTop)

	bee.addClick(self.BackButton, function()
		Game:playSound("ui_button_confirm")
		self:onBtClose()
	end)
	bee.addClick(self.ReGuideButton, function()
		Game:playSound("ui_button_confirm")
		GuideManager:startSystemGuide(17001, 0, true)
	end)

	bee.addClick(self.BetButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("football-betting-bet", self._soccerInfo.bet_id)
		self:onClickBetButton()
	end)
	bee.addClick(self.DeleteButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("football-betting-clear", self._soccerInfo.bet_id)
		self:onClickDeleteButton()
	end)
	bee.addClick(self.DetailButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("football-betting-details", self._soccerInfo.bet_id)
		self:onClickDetailButton()
	end)
	bee.addClick(self.TipsMask, function()
		Game:playSound("ui_button_confirm")
		self.BetTipsPos:SetActive(false)
	end)

	bee.addClick(self.ArrowLeft, function()
		Game:playSound("ui_button_confirm")
		self:onClickArrowLeft()
	end)
	bee.addClick(self.ArrowRight, function()
		Game:playSound("ui_button_confirm")
		self:onClickArrowRight()
	end)

	bee.addClick(self.MyBetButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("football-betting-mybet")
		UiManager:showUI("SoccerBet", {goCb = function(id)
			for k, v in pairs(self._soccerList) do
				if v.bet_id == id then
					self._selectedIndex = k
					self:evt_BetListUpdate()
					return
				end
			end
			UiManager:showToast(_T("LAB_FOOTBALL_TIPS_5"))
			self._selectedIndex = 1
			self:evt_BetListUpdate()
		end})
	end)
	bee.addClick(self.InfoButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("football-betting-rule")
		UiManager:showUI("CommonRules", {text = _T("LAB_FOOTBALL_RULES")})
	end)

	self._nodeCache = NodeCache:create()
	self._betList = {}
	self._dotItemList = {}
	self._selectedChip = 1
end

function P:onStart()
	bee.invoke(self.GoldItem, "setItemId", GPropId.Gold)
	self:evt_refreshTopInfo()

	local fun = function ()
		local startTime = 1787166000
		local endTime = 1788375540
		local serverTime = bee.getServerTime()
		if serverTime > startTime and serverTime < endTime then
			if LocalStore:isTagValid("scoccerChangeTip" .. PlayerModel:getUid()) then
				if GuideManager:isInGuide() then
					return
				end
				bee.once(0.5, function ()
					UiManager:showUI("CommonTextTipUD", {text = _T("LAB_FOOTBALL_TIPS_7"), target = self.InfoButton, adaptive = true})
				end)
			end
		end
	end

	SoccerGuessingModel:reqBetList(fun)
end

function P:onDestroy()
	if not self._soccerInfo then
		return
	end
	SoccerGuessingModel:setCheckSoccer(self._soccerInfo.bet_id)
end

function P:evt_refreshTopInfo()
	local curGold = PlayerModel:getGold()
	for k, v in pairs(self._betList) do
		curGold = curGold - v
	end
    bee.invoke(self.GoldItem, "setCount", _N2(curGold))
end

function P:evt_BetListUpdate()
	self:setSoccerList()
	-- if not self._soccerInfo then
	-- 	self:setSoccerList()
	-- else
	-- 	local info = SoccerGuessingModel:getSoccerInfo(self._soccerInfo.bet_id)
	-- 	if not info then
	-- 		return
	-- 	end
	-- 	self._soccerInfo = {}
	-- 	for k,v in pairs(info) do
	-- 		self._soccerInfo[k] = v
	-- 	end
	-- 	self:setBetInfo()
	-- end
end

function P:setSoccerList()
	self:_clearBetList()
	self._soccerList = SoccerGuessingModel:getSoccerList()
	self._maxSoccerCount = #self._soccerList

	if not self._soccerList or not next(self._soccerList) then
		self.Empty:SetActive(true)
		self.Main:SetActive(false)
		self.ReGuideButton:SetActive(false)
		return
	end

	if self._refreshSelectedIndex then
		self._refreshSelectedIndex = false
		for k,v in pairs(self._soccerList) do
			if v.bet_id == self._soccerInfo.bet_id then
				self._selectedIndex = k
			end
		end
	end
	if not self._selectedIndex then
		if self._params and self._params.jumpId then
			for k, v in pairs(self._soccerList) do
				if v == self._params.jumpId then
					self._selectedIndex = k
				end
			end
		end
	end
	if not self._selectedIndex or self._selectedIndex > self._maxSoccerCount then
		self._selectedIndex = 1
	elseif self._selectedIndex < 1 then
		self._selectedIndex = self._maxSoccerCount
	end

	local info = self._soccerList[self._selectedIndex]
	self._soccerInfo = {}
	for k,v in pairs(info) do
		self._soccerInfo[k] = v
	end
	self:setBetInfo()

	if not self.Main.activeSelf then
		self.Main:SetActive(true)
		self.Empty:SetActive(false)
		self.ReGuideButton:SetActive(true)
	end

	self.ArrowLeft:SetActive(self._maxSoccerCount > 1)
	self.ArrowRight:SetActive(self._maxSoccerCount > 1)
	self:setPageShow()

	if self._soccerInfo and self._soccerInfo.lock ~= 1 then
		GuideManager:startSystemGuide(17001, 0.65, false)
	end
end

-- 下注信息
function P:setBetInfo()
	if not self._soccerInfo then
		SoccerGuessingModel:reqBetList()
		return
	end

	local betArea = {}
	for k, v in pairs(self._soccerInfo.bet_area) do
		betArea[v.type] = v
	end
	bee.setText(self.NameTextLeft, _T(betArea[1].name))
	bee.setText(self.NameTextRight, _T(betArea[2].name))

	self.NewTag:SetActive(SoccerGuessingModel:isShowNew(self._soccerInfo.bet_id))

	-- 名字比分显示
	local index = 1
	local isShowPenaltyScore = false
	local notStart = self._soccerInfo.status == SoccerStatus.Normal and bee.getServerTime() < self._soccerInfo.game_start_time
	if notStart then
		index = 1
	elseif self._soccerInfo.status == SoccerStatus.End then
		-- 已结束
		if betArea[1].penalty_score or betArea[2].penalty_score then
			isShowPenaltyScore = true
			betArea[1].penalty_score = betArea[1].penalty_score or 0
			betArea[2].penalty_score = betArea[2].penalty_score or 0
			if betArea[1].penalty_score and betArea[1].penalty_score > 0 then
				index = 2
			elseif betArea[2].penalty_score > betArea[1].penalty_score then
				index = 3
			end
		else
			if betArea[1].regular_score and betArea[1].regular_score > 0 then
				index = 2
			elseif betArea[2].regular_score > betArea[1].regular_score then
				index = 3
			end
		end
	end
	for k,v in pairs(self.nameContList) do
		v:SetActive(k == index)
	end
	local NameCont = self.nameContList[index]
	bee.setText(self:find("NameTextLeft", NameCont), _T(betArea[1].name))
	bee.setText(self:find("NameTextRight", NameCont), _T(betArea[2].name))
	-- if notStart then
	-- 	bee.setText(self:find("ScoreTextLeft", NameCont), "?")
	-- 	bee.setText(self:find("ScoreTextRight", NameCont), "?")	
	-- elseif isShowPenaltyScore then
	-- 	bee.setText(self:find("ScoreTextLeft", NameCont), _F("LAB_FOOTBALL_20", betArea[1].regular_score, betArea[1].penalty_score))
	-- 	bee.setText(self:find("ScoreTextRight", NameCont), _F("LAB_FOOTBALL_20", betArea[2].regular_score, betArea[2].penalty_score))
	-- else
	-- 	bee.setText(self:find("ScoreTextLeft", NameCont), betArea[1].regular_score)
	-- 	bee.setText(self:find("ScoreTextRight", NameCont), betArea[2].regular_score)
	-- end

	-- 下注详情的名字显示
	bee.setText(self:find("NameText", self.TipsLeft), _T(betArea[1].name))
	bee.setText(self:find("NameText", self.TipsRight), _T(betArea[2].name))

	-- 进度条显示
	local SLIDER_MAX_LENGTH = 894
	local deltaSize = 127
	local totalAmount
	-- if self._soccerInfo.bet_type == BetType.TeamWinner then
	-- 	-- 胜负，无平局
	-- 	self.DrawSlider:SetActive(false)
	-- 	totalAmount = betArea[1].amount + betArea[2].amount
	-- 	deltaSize = 90
	-- elseif self._soccerInfo.bet_type == BetType.Draw then
	-- 	-- 胜平负
	-- 	self.DrawSlider:SetActive(true)
	-- 	totalAmount = betArea[1].amount + betArea[2].amount + betArea[3].amount

	-- 	local drawSizeDelta = self.DrawSlider.transform.sizeDelta
	-- 	local drawRate = betArea[3].amount / totalAmount
	-- 	drawSizeDelta.x = drawRate * SLIDER_MAX_LENGTH + deltaSize
	-- 	self.DrawSlider.transform.sizeDelta = drawSizeDelta
	-- 	bee.setText(self:find("CountText", self.DrawSlider), math.floor(drawRate * 100 + 0.5) .. "%")
	-- end

	totalAmount = betArea[1].amount + betArea[2].amount + (betArea[3] and betArea[3].amount or 0)

	local leftSizeDelta = self.LeftSlider.transform.sizeDelta
	local leftRate = betArea[1].amount / totalAmount
	leftSizeDelta.x = leftRate * SLIDER_MAX_LENGTH + deltaSize
	self.LeftSlider.transform.sizeDelta = leftSizeDelta
	bee.setText(self:find("CountText", self.LeftSlider), math.floor(leftRate * 100 + 0.5) .. "%")

	local rightSizeDelta = self.RightSlider.transform.sizeDelta
	local rightRate = betArea[2].amount / totalAmount
	rightSizeDelta.x = rightRate * SLIDER_MAX_LENGTH + deltaSize
	self.RightSlider.transform.sizeDelta = rightSizeDelta
	bee.setText(self:find("CountText", self.RightSlider), math.floor(rightRate * 100 + 0.5) .. "%")

	local drawSizeDelta = self.DrawSlider.transform.sizeDelta
	local drawRate = betArea[3] and (betArea[3].amount / totalAmount) or 0
	drawSizeDelta.x = drawRate * SLIDER_MAX_LENGTH + deltaSize
	self.DrawSlider.transform.sizeDelta = drawSizeDelta
	bee.setText(self:find("CountText", self.DrawSlider), math.floor(drawRate * 100 + 0.5) .. "%")

	CS.Utils.ForceRebuildLayoutImmediate(self.Slider)

	if self._timeTag then
		scheduler:removeTag(self._timeTag)
		self._timeTag = nil
	end

	if self._soccerInfo.status == SoccerStatus.End or self._soccerInfo.lock == 1 then
		self.TimeText:SetActive(true)
		self.TimeStatus1:SetActive(false)
		self.TimeStatus2:SetActive(false)
		bee.setText(self.TimeText, os.date("%Y".."/".."%m".."/".."%d %H"..":".."%M", self._soccerInfo.game_start_time))
	elseif self._soccerInfo.match_period == MatchPeriod.FirstHalf or self._soccerInfo.match_period == MatchPeriod.SecondHalf or self._soccerInfo.match_period == MatchPeriod.ExtraTime then
		self.TimeText:SetActive(false)
		self.TimeStatus1:SetActive(true)
		self.TimeStatus2:SetActive(false)

		if self._soccerInfo.add_time_second > 0 then
			local regularTime = self:_getMatchTimeStr(self._soccerInfo.regular_time_second)
			local time = self._soccerInfo.add_time_second
			bee.setText(self:find("Text", self.TimeStatus1), regularTime .. "(+" .. self:_getMatchTimeStr(time) .. ")")
			self._timeTag = self:schedule(1, function()
				time = time + 1
				bee.setText(self:find("Text", self.TimeStatus1), regularTime .. "(+" .. self:_getMatchTimeStr(time) .. ")")
			end)
		else
			local time = self._soccerInfo.regular_time_second
			bee.setText(self:find("Text", self.TimeStatus1), self:_getMatchTimeStr(time))
			self._timeTag = self:schedule(1, function()
				time = time + 1
				bee.setText(self:find("Text", self.TimeStatus1), self:_getMatchTimeStr(time))
			end)
		end
	elseif self._soccerInfo.match_period == MatchPeriod.HalfTime then
		self.TimeText:SetActive(false)
		self.TimeStatus1:SetActive(false)
		self.TimeStatus2:SetActive(true)
	else
		self.TimeText:SetActive(true)
		self.TimeStatus1:SetActive(false)
		self.TimeStatus2:SetActive(false)
		bee.setText(self.TimeText, os.date("%Y".."/".."%m".."/".."%d %H"..":".."%M", self._soccerInfo.game_start_time))
	end

	self.Lock:SetActive(self._soccerInfo.lock == 1)

	-- 下注区
	if self._soccerInfo.lock ~= 1 and self._soccerInfo.status == SoccerStatus.Normal then
		self.EmptyImg:SetActive(true)
		self.BetButton:SetActive(true)
		self.DeleteButton:SetActive(true)
	else
		self.EmptyImg:SetActive(false)
		self.BetButton:SetActive(false)
		self.DeleteButton:SetActive(false)
	end

	local curGold = PlayerModel:getGold()
	self._curBetcfg = tpl_predictor_bet[1]
	for i = #tpl_predictor_bet, 1, -1 do
		if curGold >= tpl_predictor_bet[i].balance then
			self._curBetcfg = tpl_predictor_bet[i]
			break
		end
	end

	for i,v in ipairs(self.chipList) do
		bee.setText(self:find("ChipText", v), _N(self._curBetcfg["chips" .. i]))
		self:find("Selected", v):SetActive(self._selectedChip == i)

		bee.removeAllClick(v)
		bee.addClick(v, function()
			Game:playSound("ui_button_confirm")
			if i == self._selectedChip then
				return
			end
			self._selectedChip = i
			for i1,v1 in ipairs(self.chipList) do
				self:find("Selected", v1):SetActive(self._selectedChip == i1)
			end
		end)
	end

	self:setBetCont()
end

function P:_getMatchTimeStr(seconds)
	if not seconds then
		return ""
	end
	local m = math.floor(seconds / 60)
	local s = seconds % 60
	return string.format("%02d:%02d", m, s)
end

function P:setBetCont(betArea)
	if not betArea then
		betArea = {}
		for k, v in pairs(self._soccerInfo.bet_area) do
			betArea[v.type] = v
		end
	end

	local LeftCont = self:find("Left", self.BetCont1)
	local RightCont = self:find("Right", self.BetCont1)
	local DrawCont = self:find("Draw", self.BetCont1)

	-- if self._soccerInfo.bet_type == BetType.TeamWinner then
	-- 	self.BetCont2:SetActive(true)
	-- 	self.BetCont1:SetActive(false)
	-- 	LeftCont = self:find("Left", self.BetCont2)
	-- 	RightCont = self:find("Right", self.BetCont2)
	-- elseif self._soccerInfo.bet_type == BetType.Draw then
	-- 	self.BetCont1:SetActive(true)
	-- 	self.BetCont2:SetActive(false)
	-- 	LeftCont = self:find("Left", self.BetCont1)
	-- 	RightCont = self:find("Right", self.BetCont1)

	-- 	local DrawCont = self:find("Draw", self.BetCont1)
	-- 	self:_setBetCont(DrawCont, AreaType.Draw)
	-- end

	bee.setText(self:find("NameText", LeftCont), betArea[1].name)
	bee.setText(self:find("NameText", RightCont), betArea[2].name)
	self:_setBetCont(LeftCont, AreaType.Team1)
	self:_setBetCont(RightCont, AreaType.Team2)
	self:_setBetCont(DrawCont, AreaType.Draw)
end

function P:_setBetCont(betItem, betArea)
	local Amount = self:find("Amount", betItem)
	if self._betList[betArea] and self._betList[betArea] > 0 then
		Amount:SetActive(true)
		bee.setText(self:find("CountText", Amount), _N2(self._betList[betArea]))
	else
		Amount:SetActive(false)
	end
	bee.removeAllClick(betItem)
	bee.addClick(betItem, function()
		Game:playSound("ui_button_confirm")
		if not self._selectedChip then
			return
		end

		if not self._betList[betArea] then
			self._betList[betArea] = 0
		end

		local curGold = PlayerModel:getGold()
		for k, v in pairs(self._betList) do
			curGold = curGold - v
		end

		local curSelectedGold = self._curBetcfg["chips" .. self._selectedChip]
		if curGold - curSelectedGold >= 0 then
			self._betList[betArea] = self._betList[betArea] + curSelectedGold
			
			-- 飞金币
			if not self._flyGoldList then
				self._flyGoldList = {}
			end
			local copyFlyGold = self._nodeCache:getItem(self._selectedChip, self.chipList[self._selectedChip], self.node.transform)
			copyFlyGold.transform.position = self.chipList[self._selectedChip].transform.position
			copyFlyGold.transform.localScale = bee.v3(1, 1, 1)
			self:find("Selected", copyFlyGold):SetActive(false)
			self._flyGoldList[copyFlyGold] = bee.tween(copyFlyGold, true)
			:to(0.4, {position = betItem.transform.position, scale = 0.3})
			:onComplete(function()
				self._flyGoldList[copyFlyGold] = nil
				self._nodeCache:putItem(copyFlyGold)

				Amount:SetActive(true)
				bee.setText(self:find("CountText", Amount), _N2(self._betList[betArea]))

				curGold = curGold - curSelectedGold
				bee.invoke(self.GoldItem, "setCount", _N2(curGold))
			end)
		else
			QuickByModel:checkShowView()
		end
	end)
end

-- 下注
function P:onClickBetButton()
	if not self._betList or not next(self._betList) then
		UiManager:showToast(_T("LAB_FOOTBALL_TIPS_2"))
		return
	end
	local info = SoccerGuessingModel:getSoccerInfo(self._soccerInfo.bet_id)
	if not info then
		UiManager:showToast(_T("LAB_FOOTBALL_TIPS_5"))
		self:setSoccerList()
		return
	end

	SoccerGuessingModel:reqBet(self._soccerInfo.bet_id, self._betList)
	self._refreshSelectedIndex = true
	self:setSoccerList()
end

-- 清空
function P:onClickDeleteButton()
	self._betList = {}
	self:evt_refreshTopInfo()
	self:setBetCont()
end

-- 下注详情
function P:onClickDetailButton()
	Net:post("activity/betDetail", {bet_id = self._soccerInfo.bet_id}, function(data)
		if data.code ~= 0 then
			self.BetTipsPos:SetActive(false)
			return
		end
		self:setBetDetailInfo(data)
	end)

	self.BetTipsPos:SetActive(true)
	self:setBetTips()
end

function P:setBetTips()
	-- self.TipsDraw:SetActive(self._soccerInfo.bet_type == BetType.Draw)
	local tipsPos = self.BetTipsPos.transform.position
	local buttonPos = self.DetailButton.transform.position
	self.BetTipsPos.transform.position = bee.v3(buttonPos.x, tipsPos.y, 0)
end

function P:setBetDetailInfo(data)
	local betArea = {}
	for k, v in pairs(data.bet_area) do
		betArea[v.type] = v
	end

	self:_setBetDetailInfo(self.TipsLeft, betArea[1])
	self:_setBetDetailInfo(self.TipsRight, betArea[2])
	if betArea[3] then
		self:_setBetDetailInfo(self.TipsDraw, betArea[3])
	end
end

function P:_setBetDetailInfo(detailItem, betArea)
	local NameText = self:find("NameText", detailItem)
	local MineNumText = self:find("MineNumText", detailItem)
	local RewardNumText = self:find("RewardNumText", detailItem)
	bee.setText(MineNumText, _N2(betArea.amount))
	bee.setText(RewardNumText, _N2(betArea.reward))
end

function P:_clearBetList()
	self._betList = {}
	self:evt_refreshTopInfo()

	if not self._flyGoldList then
		return
	end
	for k, v in pairs(self._flyGoldList) do
		bee.Tween.killByTarget(k)
		self._nodeCache:putItem(k)
	end
	self._flyGoldList = {}
end

function P:onClickArrowLeft()
	SoccerGuessingModel:setCheckSoccer(self._soccerInfo.bet_id)
	self._selectedIndex = self._selectedIndex - 1
	self:setSoccerList()
end

function P:onClickArrowRight()
	SoccerGuessingModel:setCheckSoccer(self._soccerInfo.bet_id)
	self._selectedIndex = self._selectedIndex + 1
	self:setSoccerList()
end

function P:setPageShow()
	for i, v in ipairs(self._soccerList) do
		if not self._dotItemList[i] then
			local dot = CU.GameObject.Instantiate(self.Dot)
			dot.transform:SetParent(self.Page.transform)
			dot.transform.localPosition = bee.v3(0, 0, 0)
			dot.transform.localScale = bee.v3(1, 1, 1)
			self._dotItemList[i] = dot
		end
		self._dotItemList[i]:SetActive(true)
	end

	local switchCount = #self._dotItemList
	if switchCount > self._maxSoccerCount then
		for i = self._maxSoccerCount + 1, switchCount do
			self._dotItemList[i]:SetActive(false)
		end
	end

	self:refreshPageShow()
end

function P:refreshPageShow()
	for k, v in pairs(self._dotItemList) do
		self:find("On", v):SetActive(k == self._selectedIndex)
		self:find("Off", v):SetActive(k ~= self._selectedIndex)
	end
end

function P:onBtClose()
	self.BetTipsPos:SetActive(false)
	self:hideUI()
	SoccerGuessingModel:clearReddot()
end

return P