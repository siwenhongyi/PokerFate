-- ========================== 寻路工具类 ==========================
local Math = math
local Random = math.random
local RandomSeed = os.time() -- 初始化随机种子
math.randomseed(RandomSeed)

-- 向量工具 (简化版，仅用于本示例)
local Vec2 = {}
Vec2.__index = Vec2

function Vec2.new(x, y)
    return setmetatable({x = x or 0, y = y or 0}, Vec2)
end

function Vec2.distance(a, b)
    local dx = a.x - b.x
    local dy = a.y - b.y
    return Math.sqrt(dx*dx + dy*dy)
end

function Vec2.lerp(a, b, t)
    return Vec2.new(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t
    )
end

-- 优先队列 (最小堆) 实现，用于 A*
local PriorityQueue = {}
PriorityQueue.__index = PriorityQueue

function PriorityQueue.new()
    return setmetatable({heap = {}, size = 0}, PriorityQueue)
end

function PriorityQueue:push(item, priority)
    self.size = self.size + 1
    local node = {item = item, priority = priority}
    self.heap[self.size] = node
    
    -- 上浮
    local i = self.size
    while i > 1 do
        local parent = Math.floor(i / 2)
        if self.heap[parent].priority > node.priority then
            self.heap[i], self.heap[parent] = self.heap[parent], self.heap[i]
            i = parent
        else
            break
        end
    end
end

function PriorityQueue:pop()
    if self.size == 0 then return nil end
    local top = self.heap[1]
    self.heap[1] = self.heap[self.size]
    self.heap[self.size] = nil
    self.size = self.size - 1
    
    -- 下沉
    local i = 1
    while true do
        local left = i * 2
        local right = i * 2 + 1
        local smallest = i
        
        if left <= self.size and self.heap[left].priority < self.heap[smallest].priority then
            smallest = left
        end
        if right <= self.size and self.heap[right].priority < self.heap[smallest].priority then
            smallest = right
        end
        
        if smallest ~= i then
            self.heap[i], self.heap[smallest] = self.heap[smallest], self.heap[i]
            i = smallest
        else
            break
        end
    end
    return top.item
end

local PINBALL_COLORS = {
	[1] = "Pinball[pinball_record_cube_01]",
	[2] = "Pinball[pinball_record_cube_02]",
	[3] = "Pinball[pinball_record_cube_02]",
	[4] = "Pinball[pinball_record_cube_03]",
	[5] = "Pinball[pinball_record_cube_03]",
	[6] = "Pinball[pinball_record_cube_03]",
	[7] = "Pinball[pinball_record_cube_02]",
	[8] = "Pinball[pinball_record_cube_02]",
	[9] = "Pinball[pinball_record_cube_01]",
}

local P = class("Pinball", UiBase)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Left = self:find("Left", AnimRoot)
	local Machine = self:find("Machine", Left)

	local Screen = self:find("Screen", Machine)
	local Pillars = self:find("Pillars", Screen)
	self.pillarList = {}
	for i = 1, Pillars.transform.childCount do
		local Line = Pillars.transform:GetChild(i - 1)
		local y = tonumber(string.replace(Line.name, "Line"))
		if not self.pillarList[y] then
			self.pillarList[y] = {}
		end
		for j = 1, Line.transform.childCount do
			local Pillar = Line.transform:GetChild(j - 1)
			local x = tonumber(string.replace(Pillar.name, "Pillar", ""))
			self.pillarList[y][x] = Pillar
		end
	end
	self.Hole = self:find("Hole", Screen)
	self.Ball = self:find("pinball_machine_ball", Screen)
	self.Ball:SetActive(false)
	local Cube = self:find("Cube", Screen)
	self.exportList = {}
	for i = 1, 9 do
		table.insert(self.exportList, self:find("Export" .. i, Cube))
	end
	self.GainAnimText = self:find("GainAnimText", Screen)
	self.GainAnimText:SetActive(false)

	self.Balance = self:find("Balance", Machine)
	self.BalanceNumText = self:find("Balance/BalanceNumText", Machine)
	self.TotalBettingNumText = self:find("TotalBetting/TotalBettingNumText", Machine)
	self.Profit = self:find("Profit", Machine)
	self.ProfitNumText = self:find("Profit/ProfitNumText", Machine)

	self.Betting = self:find("Betting", Machine)
	self.BettingFilter = self:find("BettingFilter", self.Betting)
	self.BettingFilterItem = self:find("BettingFilterItem", self.Betting)
	self.BettingFilter:SetActive(false)
	self.BettingFilterItem:SetActive(false)
	self.BettingNumText = self:find("BettingNumText", self.Betting)
	self.BettingFilterButton = self:find("BettingFilterButton", self.Betting)
	self.BettingArrowUp = self:find("BettingArrowUp", self.BettingFilterButton)
	self.BettingArrowDown = self:find("BettingArrowDown", self.BettingFilterButton)
	self.BettingArrowUp:SetActive(true)
	self.BettingArrowDown:SetActive(false)

	self.Quantity = self:find("Quantity", Machine)
	self.QuantityFilter = self:find("QuantityFilter", self.Quantity)
	self.QuantityFilterItem = self:find("QuantityFilterItem", self.Quantity)
	self.QuantityFilter:SetActive(false)
	self.QuantityFilterItem:SetActive(false)
	self.QuantityNumText = self:find("QuantityNumText", self.Quantity)
	self.QuantityFilterButton = self:find("QuantityFilterButton", self.Quantity)
	self.QuantityArrowUp = self:find("QuantityArrowUp", self.QuantityFilterButton)
	self.QuantityArrowDown = self:find("QuantityArrowDown", self.QuantityFilterButton)
	self.QuantityArrowUp:SetActive(true)
	self.QuantityArrowDown:SetActive(false)

	local Lottery = self:find("Lottery", Machine)
	self.LotteryButton = self:find("LotteryButton", Lottery)
	self.LotteryTips = self:find("LotteryTips", Lottery)

	self.OptionButton = self:find("OptionButton", Machine)
	self.CloseButton = self:find("CloseButton", Machine)

	self.HistoricalRecords = self:find("HistoricalRecords", Left)
	self.HistoricalRecords:SetActive(false)
	bee.emit("evt_sideGameRecords", false)

	self.TipMask = self:find("TipMask", Left)
	self.TipMask:SetActive(false)

	self.BallRecord = self:find("BallRecord", Left)
	self.BallRecord:SetActive(false)

	self.BallRecordScrollList = self:find("BallRecordScrollList", Left)
	self.BallRecordScrollList:SetActive(false)

	self.RulesTip = self:find("RulesTip", Left)
	self.OptionList = self:find("OptionList", Left)
	self.RecordButton = self:find("RecordButton", self.OptionList)
	self.InfoButton = self:find("InfoButton", self.OptionList)

	self._ballMsg = nil
	self.Sign = false
	self._cacheLvlId = 0

	bee.addClick(self.CloseButton, function()
		UiManager:hideUI("SideGameView")
		self:checkPushGift(self._curLvl)
	end)
	bee.addClick(self.LotteryButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickLottery()
	end)

    bee.addClick(self:find("Mask", AnimRoot), function()
        if self.HistoricalRecords.activeSelf then
        	Game:playSound("ui_button_disabled")
            self.HistoricalRecords:SetActive(false)
			bee.emit("evt_sideGameRecords", false)
            return
        end
        bee.emit("evt_hideSideGame")
		self:checkPushGift(self._curLvl)
    end)
    bee.addClick(self.TipMask, function()
    	Game:playSound("ui_button_disabled")
        self.TipMask:SetActive(false)
        if self.BallRecord.activeSelf or self.BallRecordScrollList.activeSelf then
            self._selectedRecord = nil
             self.ListRecord:refreshShowingUi()
        end
        self.BallRecord:SetActive(false)
        self.BallRecordScrollList:SetActive(false)
        self.RulesTip:SetActive(false)
        self.OptionList:SetActive(false)
    end)
    self.OptionButton = self:find("OptionButton", Machine)
    bee.addClick(self.OptionButton, function()
        Game:playSound("ui_button_confirm")
        self.TipMask:SetActive(true)
        self.OptionList:SetActive(true)
        bee.logEvent("pinball-menu")
    end)
    bee.addClick(self:find("InfoButton", self.OptionList), function()
    	Game:playSound("ui_button_confirm")
        bee.logEvent("pinball-rules")
        self.OptionList:SetActive(false)
        self.RulesTip:SetActive(true)
    end)
    bee.addClick(self:find("RecordButton", self.OptionList), function()
    	Game:playSound("ui_button_confirm")
        bee.logEvent("pinball-history")
        self.TipMask:SetActive(false)
        self.OptionList:SetActive(false)
        self:showRecords()
    end)

    bee.addClick(self.BettingFilterButton, function()
    	Game:playSound("ui_button_confirm")
    	self:onClickBettingFilterButton()
	end)
	bee.addClick(self:find("pinball_betting_bg", self.Betting), function()
		Game:playSound("ui_button_confirm")
		self:onClickBettingFilterButton()
	end)

	bee.addClick(self.QuantityFilterButton, function()
		Game:playSound("ui_button_confirm")
    	self:onClickQuantityFilterButton()
	end)
	bee.addClick(self:find("pinball_quantity_bg", self.Quantity), function()
		Game:playSound("ui_button_confirm")
		self:onClickQuantityFilterButton()
	end)

	self.FilterCloseMask = self:find("FilterCloseMask")
	self.FilterCloseMask:SetActive(false)
	bee.addClick(self.FilterCloseMask, function()
		if self.BettingFilter.activeSelf then
			self:onClickBettingFilterButton()
		end
		if self.QuantityFilter.activeSelf then
			self:onClickQuantityFilterButton()
		end
	end)
end

function P:onShow()
	self.HistoricalRecords:SetActive(false)
	bee.emit("evt_sideGameRecords", false)
	self.BallRecord:SetActive(false)
	self.BallRecordScrollList:SetActive(false)
    self._recordDatas = {}
end

function P:afterShow()
    if LocalStore:isTagValid("color_game_menu_tip" .. PlayerModel:getUid()) then
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_COLORGAME_030"), target = self.OptionButton})
    end
end

function P:onStart()
	self._openAnim, self._closeAnim = "UI_1_Pinball_into", "UI_1_Pinball_back"

	self._totalBetting = 0
	self._selectChip = 0
	self._selectQuantity = 0
	self._gold = PlayerModel:getGold()
	bee.setText(self.BalanceNumText, _N2(self._gold))
	bee.setText(self.ProfitNumText, 0)

	SideGameModel:reqGetSideGameConfREQ()
end

function P:evt_setPinballConf()
	self._isInit = true
	self:initExports()
	self:initBettingCont()
	self:initQuantityCont()
	self:refreshBettingNum()
end

function P:onDestroy()
	SettingModel:setIsStopRefreshGold(nil)
	if self._profitTween then
		self._profitTween:Kill()
		self._profitTween = nil
	end
	if self._balanceTween then
		self._balanceTween:Kill()
		self._balanceTween = nil
	end
end

function P:evt_refreshTopInfo()
	if self._isPlaying then
		return
	end
	bee.setText(self.BalanceNumText, _N2(PlayerModel:getGold()))
end

-- ================================ 界面处理 ================================

function P:initBettingCont()
	local curGold = PlayerModel:getGold()
	local cfg = SideGameModel:getPinballConf()
	for i = #cfg, 1, -1 do
		if curGold >= cfg[i].balance then
			self._chips = cfg[i].chips
			self._curLvl = cfg[i].id
			break
		end
	end

	if self._bettingItemList then
		for i = #self._bettingItemList, 1, -1 do
			CU.GameObject.Destroy(self._bettingItemList[i].item)
		end
	end
	self._bettingItemList = {}

	self._selectChip = self._chips[1]
	for i, v in ipairs(self._chips) do
		local copyBettingItem = CU.GameObject.Instantiate(self.BettingFilterItem)
		copyBettingItem.transform:SetParent(self.BettingFilter.transform)
		copyBettingItem.transform.localPosition = bee.v3(0, 0, 0)
		copyBettingItem.transform.localScale = bee.v3(1, 1, 1)
		copyBettingItem:SetActive(true)

		bee.setText(self:find("NumText", copyBettingItem), _N2(v))
		bee.setText(self:find("SelectedBg/SelectedNumText", copyBettingItem), _N2(v))
		bee.addClick(copyBettingItem, function()
			Game:playSound("ui_button_confirm")
			self._selectChip = v
			bee.setText(self.BettingNumText, _N2(self._selectChip))
			self:refreshBettingFilterItem()
			self:onClickBettingFilterButton()
			self:refreshBettingNum()
		end)

		table.insert(self._bettingItemList, {item = copyBettingItem, chip = v})
	end
	self:refreshBettingFilterItem()
	bee.setText(self.BettingNumText, _N2(self._selectChip))
	self:refreshBettingNum()
end

function P:checkBettingChips()
	local lvl
	local curGold = PlayerModel:getGold()
	local cfg = SideGameModel:getPinballConf()
	for i = #cfg, 1, -1 do
		if curGold >= cfg[i].balance then
			lvl = cfg[i].id
			break
		end
	end
	if lvl ~= self._curLvl then
		self:initBettingCont()
	end
end

function P:onClickBettingFilterButton()
	if self.BettingFilter.activeSelf then
		self.BettingFilter:SetActive(false)
		self.BettingArrowUp:SetActive(true)
		self.BettingArrowDown:SetActive(false)
		self.FilterCloseMask:SetActive(false)
		self.BettingFilter.transform:SetParent(self.Betting.transform)
	else
		bee.logEvent("pinball-bet")
		self.BettingFilter:SetActive(true)
		self.BettingArrowUp:SetActive(false)
		self.BettingArrowDown:SetActive(true)
		self.FilterCloseMask:SetActive(true)
		self.BettingFilter.transform:SetParent(self.FilterCloseMask.transform)		
	end
end

function P:refreshBettingFilterItem()
	for k,v in pairs(self._bettingItemList) do
		self:find("SelectedBg", v.item):SetActive(self._selectChip == v.chip)
	end
end

function P:initQuantityCont()
	self._quantityItemList = {}
	local balls = SideGameModel:getPinballBalls()
	self._selectQuantity = balls[1]
	for i, v in ipairs(balls) do
		local copyQuantityItem = CU.GameObject.Instantiate(self.QuantityFilterItem)
		copyQuantityItem.transform:SetParent(self.QuantityFilter.transform)
		copyQuantityItem.transform.localPosition = bee.v3(0, 0, 0)
		copyQuantityItem.transform.localScale = bee.v3(1, 1, 1)
		copyQuantityItem:SetActive(true)

		bee.setText(self:find("NumText", copyQuantityItem), v)
		bee.setText(self:find("SelectedBg/SelectedNumText", copyQuantityItem), v)
		bee.addClick(copyQuantityItem, function()
			Game:playSound("ui_button_confirm")
			self._selectQuantity = v
			bee.setText(self.QuantityNumText, self._selectQuantity)
			self:refreshQuantityFilterItem()
			self:onClickQuantityFilterButton()
			self:refreshBettingNum()
		end)

		table.insert(self._quantityItemList, {item = copyQuantityItem, count = v})
	end
	self:refreshQuantityFilterItem()
	bee.setText(self.QuantityNumText, self._selectQuantity)
end

function P:refreshQuantityFilterItem()
	for k,v in pairs(self._quantityItemList) do
		self:find("SelectedBg", v.item):SetActive(self._selectQuantity == v.count)
	end
end

function P:onClickQuantityFilterButton()
	if self.QuantityFilter.activeSelf then
		self.QuantityFilter:SetActive(false)
		self.QuantityArrowUp:SetActive(true)
		self.QuantityArrowDown:SetActive(false)
		self.FilterCloseMask:SetActive(false)
		self.QuantityFilter.transform:SetParent(self.Quantity.transform)
	else
		bee.logEvent("pinball-balls")
		self.QuantityFilter:SetActive(true)
		self.QuantityArrowUp:SetActive(false)
		self.QuantityArrowDown:SetActive(true)
		self.FilterCloseMask:SetActive(true)
		self.QuantityFilter.transform:SetParent(self.FilterCloseMask.transform)		
	end
end

function P:initExports()
	local exportConf = SideGameModel:getExportConf()
	for i, v in ipairs(exportConf) do
		bee.setText(self:find("Ani_root/ExportNum", self.exportList[i]), v .. "x")
	end
end

-- 刷新总下注数
function P:refreshBettingNum()
	self._totalBetting = self._selectChip * self._selectQuantity
	bee.setText(self.TotalBettingNumText, _N2(self._totalBetting))
end

-- 点击开始
function P:onClickLottery()
	if not self._isInit then
		return
	end
	if self._isPlaying then
		return
	end

	if not bee.checkCd("pinball_lottery", 2) then
        return
    end

	self._gold = PlayerModel:getGold()
	self._beatGold = self._selectChip * self._selectQuantity
	-- 判断余额
	if self._selectChip * self._selectQuantity > PlayerModel:getGold() then
		UiManager:showToast(_T("LAB_PINBALL_14"))
		self._beatTotalGold = 0
		QuickByModel:checkShowView(GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME)
		return
	end

	SettingModel:setIsStopRefreshGold(true)

	local params = {}
	params.from_game_type = GameModel.data and GameModel.data:getGameType() or 0
	params.lvl = self._curLvl
	params.per_bet = self._selectChip
	params.ball_num = self._selectQuantity
	Net:sendReq("pb.PinballActionREQ", params)

	self._isPlaying = true
	self:find("pinball_lottery_button_on", self.LotteryButton):SetActive(false)
	self.LotteryButton.transform:GetComponent("Button").enabled = false
	self.LotteryButton.transform:GetComponent("ButtonZoom").enabled = false
	self.LotteryTips:SetActive(false)
end

-- 断线重连
function P:evt_UserLoginRSP()
	if self._beginAnim then
		return
	end

	self._isPlaying = false
	self:find("pinball_lottery_button_on", self.LotteryButton):SetActive(true)
	self.LotteryButton.transform:GetComponent("Button").enabled = true
	self.LotteryButton.transform:GetComponent("ButtonZoom").enabled = true
	self.LotteryTips:SetActive(true)
end

function P:evt_PinballActionRSP(msg)
	if msg.code ~= 0 then
		self._isPlaying = false
		self:find("pinball_lottery_button_on", self.LotteryButton):SetActive(true)
		self.LotteryButton.transform:GetComponent("Button").enabled = true
		self.LotteryButton.transform:GetComponent("ButtonZoom").enabled = true
		self.LotteryTips:SetActive(true)
		return
	end

	self.Sign = true

	local curGold = self._gold - self._beatGold
	bee.setText(self.BalanceNumText, _N2(curGold))
	bee.setText(self.ProfitNumText, 0)

	self._ballMsg = msg
	local balls = msg.action_result.balls

	local totalReward = 0
	for i,v in ipairs(balls) do
		totalReward = totalReward + v.reward
	end
	
	local effName
	if totalReward > self._beatGold * 5 then
		effName = "Prefab/Pinball/Eff_poker_Ui_pinball_chouma04"
	elseif totalReward > self._beatGold * 3  then
		effName = "Prefab/Pinball/Eff_poker_Ui_pinball_chouma03"
	elseif totalReward > self._beatGold * 2 then
		effName = "Prefab/Pinball/Eff_poker_Ui_pinball_chouma02"
	else
		effName = "Prefab/Pinball/Eff_poker_Ui_pinball_chouma01"
	end

	self._beginAnim = true
	self._waitBallCount = 0
	self._beginProfit = 0
	self._ballCount = #balls
	local animDetailTime = msg.action_result.ball_fire_interval / 1000
	for i = 1, self._ballCount do
		self:once((i - 1) * animDetailTime, function()
			local exportId = balls[i].export_id
			local goldParams = {}
			goldParams.beginGold = curGold
			goldParams.profit = balls[i].reward
			goldParams.effName = effName
			self:beginDropAnim(exportId, goldParams)
		end)
	end

	-- 添加记录
	if self._recordDatas then
		local params = {}
		params.index = #self._recordDatas + 1
		params.bet_result = {}
		params.bet_data = {
			chips = self._beatGold,
			profit = 0,
			num = #balls,
		}
		local exportConf = SideGameModel:getExportConf()
		for i = 1, params.bet_data.num do
			-- 记录
			table.insert(params.bet_result, {export_id = balls[i].export_id, rate = exportConf[balls[i].export_id]})
			params.bet_data.profit = params.bet_data.profit + balls[i].profit
		end
		table.insert(self._recordDatas, 1, params)
		if #self._recordDatas > tpl_constdata.Pinball_History_Limit then
			table.remove(self._recordDatas)
		end

		for k, v  in ipairs(self._recordDatas) do
			v.index = k
		end
	end

	self._beatGold = 0
end

-- ================================ 弹球动画 ================================

-- 下落动画
function P:beginDropAnim(exportId, goldParams)
	local endIndex = exportId * 2
	local width, height = 19, 18
	local grid = self:initGrid(width, height, endIndex)

	local startPos = {x = math.ceil(width / 2), y = 1}
	local targetPos = {x = endIndex, y = height}
	local rawPath = self:findRandomPath(grid, width, height, startPos, targetPos)
	if not rawPath then
		-- 边界情况下随机阻塞点可能导致无法生成路径，则重新寻路
		for i = 1, 20 do
			grid = self:initGrid(width, height, endIndex)
			rawPath = self:findRandomPath(grid, width, height, startPos, targetPos)
			if rawPath then
				break
			end
		end
	end

	local lineList = {{startPos.x}}
	-- 记录每行移动的格子
	for i = 2, #rawPath do
		if not lineList[rawPath[i].y] then
			lineList[rawPath[i].y] = {}
		end
		table.insert(lineList[rawPath[i].y], rawPath[i].x)
	end

	-- 根据路径生成动画列表
	local animList = {}
	local randTime = math.random(-60, 60)
	local bezierTime = 0.3 + randTime / 1000
	local strightTime = 0.1
	local crossTime = 0.3
	local finalTime = 10

	-- 出生动画
	local outTemp = {}
	outTemp.startGrid = startPos
	outTemp.startPos = self.Hole.transform.position
	outTemp.endGrid = {y = 2, x = outTemp.startGrid.x}
	outTemp.isStright = true
	outTemp.bottomTarget = self.pillarList[outTemp.endGrid.y + 1][outTemp.startGrid.x]
	local endTarget = self.pillarList[outTemp.endGrid.y + 1][outTemp.endGrid.x]
	outTemp.endPos = {x = endTarget.transform.position.x, y = endTarget.transform.position.y + 0.2}
	outTemp.dir = 0
	outTemp.detailTime = strightTime
	table.insert(animList, outTemp)

	local animCount = 1
	for i = 3, #lineList do
		local temp = {}
		if #lineList[i] >= 3 then
			-- 横跨几个柱子，分两段动画
			-- 先下降
			local temp1 = {}
			temp1.startGrid = animList[animCount].endGrid
			temp1.startPos = animList[animCount].endPos
			temp1.endGrid = {y = i, x = lineList[i][1]}
			if temp1.endGrid.x > temp1.startGrid.x then
				temp1.dir = 1
			elseif temp1.endGrid.x < temp1.startGrid.x then
				temp1.dir = -1
			else
				temp1.dir = 0
			end
			local crossDir
			if lineList[i][2] - lineList[i][1] > 0 then
				crossDir = 1
			elseif lineList[i][1] - lineList[i][2] > 0 then
				crossDir = -1
			else
				crossDir = 0
			end
			temp1.isBezier = true
			if self.pillarList[temp1.startGrid.y + 1] then
				temp1.bottomTarget = self.pillarList[temp1.startGrid.y + 1][temp1.startGrid.x]
			end
			local endTarget = self.pillarList[i + 1][temp1.endGrid.x]
			temp1.endPos = {x = endTarget.transform.position.x + crossDir * 0.2, y = endTarget.transform.position.y + 0.2}
			temp1.detailTime = bezierTime

			table.insert(animList, temp1)
			animCount = animCount + 1

			-- 再横跨
			for j = 2, #lineList[i] - 1, 2 do
				local temp2 = {}
				temp2.startGrid = animList[animCount].endGrid
				temp2.startPos = animList[animCount].endPos
				temp2.dir = crossDir
				temp2.endGrid = {y = i, x = lineList[i][j] + temp2.dir}
				local endTarget = self.pillarList[i + 1][temp2.endGrid.x]
				temp2.endPos = {x = endTarget.transform.position.x, y = endTarget.transform.position.y + 0.2}
				if self.pillarList[temp2.startGrid.y + 1] then
					temp2.bottomTarget = self.pillarList[temp2.startGrid.y + 1][temp2.startGrid.x]
				end
				temp2.isCross = true
				temp2.detailTime = crossTime

				table.insert(animList, temp2)
				animCount = animCount + 1
			end
		elseif self.pillarList[i + 1] then
			temp.startGrid = animList[animCount].endGrid
			temp.startPos = animList[animCount].endPos
			temp.endGrid = {y = i, x = lineList[i][1]}

			temp.isBezier = true
			if self.pillarList[temp.startGrid.y + 1] then
				temp.bottomTarget = self.pillarList[temp.startGrid.y + 1][temp.startGrid.x]
			end
			local endTarget = self.pillarList[i + 1][temp.endGrid.x]
			temp.endPos = {x = endTarget.transform.position.x, y = endTarget.transform.position.y + 0.2}

			if temp.endGrid.x > temp.startGrid.x then
				temp.dir = 1
			elseif temp.endGrid.x < temp.startGrid.x then
				temp.dir = -1
			else
				temp.dir = 0
			end
			temp.detailTime = bezierTime

			table.insert(animList, temp)
			animCount = animCount + 1
		end
	end

	-- 进入最终位置
	local inTemp = {}
	inTemp.startGrid = animList[animCount].endGrid
	inTemp.startPos = animList[animCount].endPos
	inTemp.endGrid = {y = height, x = lineList[#lineList][1]}
	inTemp.bottomTarget = self.pillarList[inTemp.startGrid.y + 1][inTemp.startGrid.x]
	inTemp.isBezier = true
	local endTarget = self.exportList[exportId]
	inTemp.endPos = {x = endTarget.transform.position.x, y = endTarget.transform.position.y + 0.2}
	if inTemp.endGrid.x > inTemp.startGrid.x then
		inTemp.dir = 1
	elseif inTemp.endGrid.x < inTemp.startGrid.x then
		inTemp.dir = -1
	else
		inTemp.dir = 0
	end
	table.insert(animList, inTemp)
	animCount = animCount + 1
	inTemp.detailTime = bezierTime

	-- 结算动画
	local finalTemp = {}
	finalTemp.isFinal = true
	finalTemp.detailTime = finalTime
	table.insert(animList, finalTemp)
	animCount = animCount + 1

	local copyBall = CU.GameObject.Instantiate(self.Ball.gameObject)
	copyBall.transform:SetParent(self.Ball.transform.parent)
	copyBall.transform.localScale = bee.v3(0.8, 0.8, 1)
	copyBall:SetActive(true)
	copyBall.transform.position = self.Hole.transform.position

	local animTime = 0
	for i = 1, animCount do
		self:once(animTime, function()
			if animList[i].isBezier then
				local centerPos = bee.v3(animList[i].startPos.x + animList[i].dir * 0.1, animList[i].startPos.y + 0.3 + math.random(-70, 70) / 1000, 0)
				AnimationMgr:playBezierFlight(copyBall, bee.v3(animList[i].endPos.x, animList[i].endPos.y, 0), nil, {time = animList[i].detailTime, centerPos = centerPos})
				if animList[i].bottomTarget then
					self:once(0.05, function()
						if not self._ishide then
							Game:playSound("sound_Pinball_hit")
							AnimationMgr:playUIEffect("Prefab/Pinball/Eff_poker_Pinball_ks", animList[i].bottomTarget.transform, bee.v3(0, 0, 0))
						end
					end)
				end
			elseif animList[i].isCross then
				local centerPos = bee.v3(animList[i].startPos.x + animList[i].dir * 0.1, animList[i].startPos.y + 0.4, 0)
				AnimationMgr:playBezierFlight(copyBall, bee.v3(animList[i].endPos.x, animList[i].endPos.y, 0), nil, {time = animList[i].detailTime, centerPos = centerPos})
				if animList[i].bottomTarget then
					self:once(0.05, function()
						if not self._ishide then
							Game:playSound("sound_Pinball_hit")
							AnimationMgr:playUIEffect("Prefab/Pinball/Eff_poker_Pinball_ks", animList[i].bottomTarget.transform, bee.v3(0, 0, 0))
						end
					end)
				end
			elseif animList[i].isStright then
				AnimationMgr:playStraightFlight(copyBall, animList[i].endPos, nil, {time = animList[i].detailTime})
			elseif animList[i].isFinal then
				-- 结算动画
				CU.GameObject.Destroy(copyBall)
				local exportTarget = self:find("Ani_root", self.exportList[exportId])
				AnimationMgr:playAnim(exportTarget, "UI_1_Pinball_Cube_ani")
				if exportId == 1 or exportId == 10 then
					if not self._ishide then
						AnimationMgr:playUIEffect("Prefab/Pinball/Eff_poker_Pinball_zj", self.exportList[exportId].transform, bee.v3(0, 0, 0))
					end
				end
				if not self._ishide then
					if exportId == 1 or exportId == 9 then
						Game:playSound("sound_Pinball_high")
					elseif exportId == 2 or exportId == 3 or exportId == 8 or exportId == 7 then
						Game:playSound("sound_Pinball_middle")
					else
						Game:playSound("sound_Pinball_low")
					end
				end

				self:once(0.2, function()
					local copyGainAnimText = CU.GameObject.Instantiate(self.GainAnimText)
					copyGainAnimText.transform:SetParent(self.GainAnimText.transform.parent)
					copyGainAnimText.transform.localScale = bee.v3(1, 1, 1)
					local exportTargetPos = self.exportList[exportId].transform.position
					copyGainAnimText.transform.position = bee.v3(exportTargetPos.x, exportTargetPos.y + 0.4, 0)
					bee.setText(self:find("Ani_GainAnimText", copyGainAnimText), "+" .. _N2(goldParams.profit))
					copyGainAnimText:SetActive(true)
					self:once(1, function()
						CU.GameObject.Destroy(copyGainAnimText)
					end)
					self:once(0.4, function()
						self._waitBallCount = self._waitBallCount + 1
						self:endDropAnim(goldParams)
					end)
				end)
			end
		end)
		animTime = animTime + animList[i].detailTime
	end
end

function P:endDropAnim(goldParams)
	if self._profitTween then
		self._profitTween:Kill()
		self._profitTween = nil
	end
	bee.setText(self.ProfitNumText, _N2(self._beginProfit))
	self._profitTween = bee.Tween.toFloat(self._beginProfit, self._beginProfit + goldParams.profit, 0.4, function(v)
			bee.setText(self.ProfitNumText, _N2(math.floor(v)))
		end)
	self._beginProfit = self._beginProfit + goldParams.profit

	self._cacheLvlId = self._curLvl
	-- 本次抽奖结束
	if self._waitBallCount == self._ballCount then
		self:once(0.4, function()
			if self.ListRecord and self._recordDatas then
				self.ListRecord:setDatas(self._recordDatas)
			end

			if self._balanceTween then
				self._balanceTween:Kill()
				self._balanceTween = nil
			end

			local deltaTime = 0
			local curGold = PlayerModel:getGold()
			if goldParams.effName and not self._ishide then
				self._flyGoldEff = AnimationMgr:playUIEffect(goldParams.effName, self.Profit.transform, bee.v3(0, 21, 0))
				deltaTime = 0.5
			end
			self:once(deltaTime, function()
				self._balanceTween = bee.Tween.toFloat(goldParams.beginGold, curGold, 0.3, function(v)
					bee.setText(self.BalanceNumText, _N2(math.floor(v)))
					if v == curGold then
						self._balanceTween = nil
					end
				end)
				bee.vibrate(tpl_vibrate["shock_pinball"])
				self._isPlaying = false
				self._beginAnim = false
			end)

			self:find("pinball_lottery_button_on", self.LotteryButton):SetActive(true)
			self.LotteryButton.transform:GetComponent("Button").enabled = true
			self.LotteryButton.transform:GetComponent("ButtonZoom").enabled = true
			self.LotteryTips:SetActive(true)

			self:checkBettingChips()
			SettingModel:setIsStopRefreshGold(nil)
			--判定礼包推送
			self:checkPushGift(self._cacheLvlId)
			--盈利事件
			if self._beginProfit > self._totalBetting then
				bee.emit("evt_PinballWin")
			end
		end)
	end
end

function P:initGrid(width, height, endIndex)
	local grid = {}
	local c = math.ceil(width / 2)
	-- 1 = 障碍， 0 = 可通行
	for y = 1, height do
		grid[y] = {}
		for x = 1, width do
			if y == 1 then
				if x == c then
					grid[y][x] = 0
				else
					grid[y][x] = 1
				end
			elseif y < height then
				local c1 = math.ceil(y / 2)
				if x < (c - c1) or x > (c + c1) then
					grid[y][x] = 1
				elseif self.pillarList[y] and self.pillarList[y][x] then
					grid[y][x] = 1
				else
					grid[y][x] = 0
				end
			else
				if x % 2 == 0 then
					grid[y][x] = 0
				else
					grid[y][x] = 1
				end
			end
		end
	end

	-- -- 边界处理：随机生成几个边界障碍点，避免固定走最短路径
	-- if endIndex == 2 then
	-- 	for k, v in pairs(self.pillarList) do
	-- 		if (k < (height - 5)) then
	-- 			local randBlock = math.random(0, 1)
	-- 			if randBlock == 1 then
	-- 				grid[k][c - math.floor(k / 2) + math.random(0, 1)] = 1
	-- 				grid[k][c - math.floor(k / 2) + math.random(0, 2)] = 1
	-- 			end
	-- 		end
	-- 	end
	-- elseif endIndex == height then
	-- 	for k, v in pairs(self.pillarList) do
	-- 		if (k < (height - 5)) then
	-- 			local randBlock = math.random(0, 1)
	-- 			if randBlock == 1 then
	-- 				grid[k][c + math.floor(k / 2) - math.random(0, 1)] = 1
	-- 				grid[k][c + math.floor(k / 2) - math.random(0, 2)] = 1
	-- 			end
	-- 		end
	-- 	end
	-- end
	return grid
end

function P:findRandomPath(grid, width, height, startPos, targetPos)
	local openSet = PriorityQueue.new()
	local closedSet = {}
	local cameFrom = {}

	-- 初始化起点
	local startId = startPos.x .. "," .. startPos.y
	local startG = 0
	local startH = Vec2.distance(Vec2.new(startPos.x, startPos.y), Vec2.new(targetPos.x, targetPos.y))

	openSet:push({x = startPos.x, y = startPos.y, g = startG, h = startH})

	-- 方向数组
	local directions = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}}

	while openSet.size > 0 do
		local current = openSet:pop()
		local currentId = current.x .. "," .. current.y

		if closedSet[currentId] then
			goto continue_loop
		end
		closedSet[currentId] = true

		-- 到达终点
		if current.x == targetPos.x and current.y == targetPos.y then
			return self:reconstructPath(cameFrom, current)
		end

		-- 遍历邻居
		for _, dir in ipairs(directions) do
			local nx = current.x + dir[1]
			local ny = current.y + dir[2]

			-- 边界检查
			if nx >= 1 and nx <= width and ny >= 1 and ny <= height then
				-- 障碍物检查
				if grid[ny][nx] == 0 then
					local neighborId = nx .. "," .. ny
					if not closedSet[neighborId] then
						local randomNoise = math.random() * 0.4 + 0.1
						local tentativeG = current.g + 1.0 + randomNoise

						if not cameFrom[neighborId] or tentativeG < (cameFrom[neighborId].g or math.huge) then
							local h = Vec2.distance(Vec2.new(nx, ny), Vec2.new(targetPos.x, targetPos.y))
							local neighbor = {x = nx, y = ny, g = tentativeG, h = h}
							neighbor.parent = current

							cameFrom[neighborId] = neighbor
							openSet:push(neighbor, tentativeG + h)
						end
					end
				end
			end
		end

		::continue_loop::
	end

	return nil
end

function P:reconstructPath(cameFrom, current)
	local path = {}
	local curr = current
	while curr do
		table.insert(path, 1, {x = curr.x, y = curr.y})
		curr = curr.parent
	end
	return path
end

function P:checkPushGift(lvlId)
	local sum = self:getGameProfit()
	QuickByModel:checkSideGame(self.Sign, sum, GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME, lvlId)
	self.Sign = false
end

function P:getGameProfit()
	local sum = 0
	if self._ballMsg == nil then
		return sum
	end
	for _,v in pairs(self._ballMsg.action_result.balls) do
		sum = sum + v.profit
	end
	return sum
end

-------------- 历史记录 start --------------
function P:showRecords()
    self.HistoricalRecords:SetActive(true)
	bee.emit("evt_sideGameRecords", true)

    if not self._initRecords then
        self._initRecords = true
        local AnimRoot = self:find("AnimRoot", self.HistoricalRecords)
        local RecordList = self:find("RecordList", AnimRoot)
        local RecordItem = self:find("RecordItem", AnimRoot)
        RecordItem:SetActive(false)

        bee.addClick(self:find("CloseButton", AnimRoot), function()
            self.HistoricalRecords:SetActive(false)
			bee.emit("evt_sideGameRecords", false)
        end)

        bee.setText(self:find("RecordsTipText", AnimRoot), _F("LAB_PINBALL_13", tpl_constdata.Pinball_History_Limit))

        self.ListRecord = UiListEx:create(RecordList)
        self.ListRecord:setWidth(60)
        self.ListRecord:setCreateFunc(function(data)
            return CU.GameObject.Instantiate(RecordItem)
        end)
        self.ListRecord:setRefreshFunc(function(data, item)
            self:find("SingleBg", item):SetActive(data.index % 2 == 1)
            self:find("SingleBg2", item):SetActive(data.index % 2 == 0)
            self:find("pinball_record_list_frame_on", item):SetActive(data == self._selectedRecord)

            bee.setText(self:find("BallCountText", item), data.bet_data.num)
            bee.setText(self:find("TotalBeaText", item), _N2(data.bet_data.chips))
            if data.bet_data.profit > 0 then
                bee.setText(self:find("ProfitText", item), _N2(data.bet_data.profit))
                bee.setText(self:find("GreyProfitText", item), "")
            else
                bee.setText(self:find("ProfitText", item), "")
                bee.setText(self:find("GreyProfitText", item), _N2(data.bet_data.profit))
            end

            bee.addClick(item, function()
            	Game:playSound("ui_button_confirm")
                self:showRecordTips(data, item)
                self.ListRecord:refreshShowingUi()
            end, true)
        end)
    end

    self.BallRecord:SetActive(false)
    self.BallRecordScrollList:SetActive(false)

    Net:sendReq("pb.GetSideGameHisRecordREQ", {game_type = GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME})
end

function P:showRecordTips(data, item)
    self.TipMask:SetActive(true)
    self._selectedRecord = data

    local recordCont

    if #data.bet_result > 10 then
    	self.BallRecordScrollList:SetActive(true)
    	if not self._recordList then
    		self:initBallRecordScrollList()
    	end
    	for i,v in ipairs(data.bet_result) do
    		v.index = i
    	end
    	self._recordList:setDatas(data.bet_result)
    	self._recordList:moveToYItem(1)
    	recordCont = self.BallRecordScrollList
    else
    	self.BallRecord:SetActive(true)

    	if not self.RecordItem then
			self.RecordItem = self:find("RecordItem", self.BallRecord)
			self.RecordItem:SetActive(false)

			self._RecordItems = {}
		end

		for _, v in pairs(self._RecordItems) do
			v:SetActive(false)
		end

		for k, v in ipairs(data.bet_result) do
			local color = PINBALL_COLORS[v.export_id] or PINBALL_COLORS[1]
			local item = self._RecordItems[k]
			if not item then
				item = CU.GameObject.Instantiate(self.RecordItem, self.BallRecord.transform, false)
				self._RecordItems[k] = item
			end
			item:SetActive(true)
			v.index = k
			self:setBallRecordItem(item, v)
		end

	    CS.Utils.ForceRebuildLayoutImmediate(self.BallRecord)
	    recordCont = self.BallRecord
    end

	local h = recordCont:GetComponent("RectTransform").rect.height
	local arrowTop = 40
    local pos = recordCont.transform.position
    pos.y = item.transform.position.y
    recordCont.transform.position = pos
    pos = recordCont.transform.localPosition
    pos.y = pos.y + 40
    local flag = false
    if pos.y - h < -529 then
        pos.y = -529 + h
        flag = true
    end
    recordCont.transform.localPosition = pos

    local TipsArrow = self:find("TipsArrow", recordCont)
    if flag or true then
        if not self._tipArrowUpPos then
            self._tipArrowUpPos = TipsArrow.transform.localPosition
        end
        local arrowPos = TipsArrow.transform.position
        arrowPos.y = item.transform.position.y
        TipsArrow.transform.position = arrowPos
    elseif self._tipArrowUpPos then
        TipsArrow.transform.localPosition = bee.v3(self._tipArrowUpPos.x, - arrowTop)
    end
end

function P:initBallRecordScrollList()
	self._recordList = UiListEx:create(self:find("RecordScrollList", self.BallRecordScrollList))
	self._recordList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self:find("RecordItem", self.BallRecord))
	end)
	self._recordList:setRefreshFunc(function(data, item)
		self:setBallRecordItem(item, data)
	end)
	self._recordList:setWidth(58.5)
	self._recordList:setTopBottom(2, 0)
end

function P:setBallRecordItem(item, data)
	local index = data.index
	local color = PINBALL_COLORS[data.export_id] or PINBALL_COLORS[1]
	self:find("SingleBg", item):SetActive(index % 2 == 1)
	self:find("SingleBg2", item):SetActive(index % 2 == 0)
	bee.setText(self:find("IndexText", item), index)
	bee.setText(self:find("ExportText", item), "" .. data.rate .. "x")
	bee.setIconInAtlas(self:find("Cube", item), color)
end

function P:evt_GetSideGameHisRecordRSP(msg)
    if msg.game_type == GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME then
        self._recordDatas = {}
        if msg.bet_data and "" ~= msg.bet_data then
            local bet_data = json.decode(msg.bet_data)
            local bet_result = json.decode(msg.result)
            for k, v in ipairs(bet_data) do
                table.insert(self._recordDatas, {
                    index = k,
                    bet_data = v,
                    bet_result = bet_result[k] or {},
                })
            end
        end
        self.ListRecord:setDatas(self._recordDatas)
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self._ishide = not isVisible
    self:clearEff()
end

function P:evt_uiBlur(flag)
	self._ishide = flag
	self:clearEff()
end

function P:evt_gameBlur(flag)
	self._ishide = flag
	self:clearEff()
end

function P:clearEff()
	if not bee.isNull(self._flyGoldEff) then
		CU.GameObject.Destroy(self._flyGoldEff)
		self._flyGoldEff = nil
	end
end

return P