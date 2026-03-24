local P = class("SpringFestivalMain", UiFullView)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)
	local LeftTop = self:find("LeftTop", self.AnimRoot)
	local RightTop = self:find("RightTop", self.AnimRoot)
	local Right = self:find("Right", self.AnimRoot)

	self.TextTime = self:find("Title/Time/Text", Center)
    self.OpenButton = self:find("Popup/OpenButton", Center)
	self.ActiveItemCount = self:find("Popup/Quantity/Value", Center)
	self.ActiveItemCountTip = self:find("Popup/Quantity/ValueTip", Center)
	self.ActiveItemIcon = self:find("Popup/Quantity/spring_main_icon_currency", Center)
	self.RecordList = self:find("Record/RecordList", Center)
	self.RecordItem = self:find("Record/RecordList/RecordItem", Center)
	self.TestText = self:find("Record/RecordList/TestText", Center):GetComponent("Text")
	self.RecordTip = self:find("Record/Text", Center)
	self.BackButton = self:find("BackButton", LeftTop)
	self.TipsButton = self:find("TipsButton", LeftTop)
	self.CurrencyButton = self:find("Currency", RightTop)
	self.CurrencyItemIcon = self:find("Currency/spring_main_icon_currency", RightTop)
	self.TextCount = self:find("Currency/Text", RightTop)
	self.LuckyBagButton = self:find("LuckyBagButton", Right)
	self.TaskButton = self:find("TaskButton", Right)
	self.Effect = self:find("Effect", self.AnimRoot)
	self.RedPacketTipButton = self:find("Character/spring_main_character_100102", Center)
	self.RedPacketTipText = self:find("Character/Text", Center)

	RedManager:bind(self:find("RedPoint", self.OpenButton), RedTag.SpringFestivalRedPacket)
	RedManager:bind(self:find("RedPoint", self.TaskButton), RedTag.SpringFestivalTask)

	self:clickActiveItem(self.ActiveItemIcon)
	self:clickActiveItem(self.CurrencyItemIcon)
	
	self.omit = false --省略名称
	self.RecordScrollRect = self.RecordList:GetComponent('ScrollRect')
	self.RecordScrollContent = self.RecordScrollRect.content
	self.limitHeight = 0

	self.tipCfg = {}
	self.tipRandomCfg = {}

	self.broadcastList = {}

	self.activeCfg = SpringFestivalModel:getActiveCfg()

	bee.addClick(self.BackButton, function()
		Game:playSound("ui_button_confirm")
		-- self:onDispose()
		self:hideUI()
	end)

	bee.addClick(self.TipsButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("SpringFestivalRules")
	end)

	bee.addClick(self.CurrencyButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("SpringFestivalTask")
		-- UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(self.activeCfg.activity_item, true)})
	end)

	bee.addClick(self.LuckyBagButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("SpringFestivalShop")
    end)

	bee.addClick(self.TaskButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("SpringFestivalTask")
    end)

	bee.addClick(self.OpenButton, function()
		Game:playSound("ui_button_confirm")
        self:openRedParket()
    end)

	bee.addClick(self.RedPacketTipButton, function()
		Game:playSound("ui_button_confirm")
		self:changeTip()
	end)

	local titleText = _T("LAB_FESTIVAL_ACTIVITY1_1")
	self.TestText.text = titleText
	if self.TestText.preferredWidth > 600 then
		self.omit = true
	end

	self.List = UiListEx:create(self.RecordList)
    self.List:setWidth(46)
    self.List:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.RecordItem)
    end)
    self.List:setRefreshFunc(function(data, item)
        self:refreshBroadcastItem(data, item)
    end)

	TaskModel:reportTask(TaskType.CheckView, TaskTargetId.SpringFestivalMain)
	-- SpringFestivalModel:reqTaskList()

	bee.logEvent("springfestival-main")
end

function P:onShow()
    P.super.onShow(self)

    -- TaskModel:reportTask(TaskType.CheckView, TaskTargetId.HotSpring)
	-- bee.setText(self.TextTime, _F("LAB_THEME_ACTIVITY_TIME", TimeHelp:getDateTimeStrM(ThemeModel._end_time, "/")))

	for _,v in pairs(tpl_festival_pool) do
		if v.publicity_pr ~= nil then
			table.insert(self.tipCfg, v)
		end
	end
	self:changeTip()

	self:evt_refreshTopInfo()
	SpringFestivalModel:reqBroadcastDatas()
end

function P:evt_refreshTopInfo()
	local itemCount = ItemModel:getItemNumById(GPropId.FestivalRedPacket)
    bee.setTextGold(self.TextCount, _N(itemCount))
	self:refreshTip(itemCount)
end
--刷新红包显示
function P:refreshTip(count)
	local suff = count >= self.activeCfg.cost[2]
	self.ActiveItemCount:SetActive(suff)
	self.ActiveItemCountTip:SetActive(not suff)
end

--点击福饰
function P:clickActiveItem(obj)
	bee.addClick(obj, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(self.activeCfg.activity_item, true), target = obj})
    end, true)
end

--检测开启红包
function P:openRedParket()
	--红包不足
	local itemCount = ItemModel:getItemNumById(GPropId.FestivalRedPacket)
	if itemCount < self.activeCfg.cost[2] then
		self:insufficientItemEvent()
		return
	end
	self.Effect:SetActive(true)
	bee.once(1.3, function()
		--发送开红包请求
		SpringFestivalModel:reqOpenRedPacket()
		bee.once(1, function()
			self.Effect:SetActive(false)
		end)
	end)
	
end

--红包不足反馈
function P:insufficientItemEvent()
	UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self.activeCfg.activity_item].name)))
	UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(self.activeCfg.activity_item, true)})
end

function P:evt_springFestivalItemInsufficient()
	self:insufficientItemEvent()
end

function P:evt_getBroadcastDatas(list)
	self.broadcastList = list or {}
	local count = table.nums(list)
	self.RecordTip:SetActive(count == 0)
	if count > 0 and count <= 3 then
		self.List:setDatas(list)
	elseif count > 3 then
		local cacheList = {}
		table.insert(cacheList, {})
		table.insert(cacheList, {})
		for _ = 1, 2 do
			for j = 1, #list do
				table.insert(cacheList, list[j])
			end
		end
		self.List:setDatas(cacheList)
		self.limitHeight = self.RecordScrollContent.sizeDelta.y * 0.5 + 46
		bee.schedule(0.05, function() self:loopEvent() end, self.node)
	end
end

function P:evt_refreshBroadcast(itemData)
	local data = {}
	data.nickname = PlayerModel:getName()
	data.item_list = itemData
	table.insert(self.broadcastList, data)
	self:evt_getBroadcastDatas(self.broadcastList)
end

--设置广播内容
function P:refreshBroadcastItem(data, item)
	if not next(data) then
		bee.setText(self:find("Root/Text", item), "")
		self:find("Root/Icon", item):SetActive(false)
		return
	end

	local name = data.nickname
	if self.omit then
		self.TestText.text = data.nickname
		if self.TestText.preferredWidth > 160 then
			name = ""
			local charCount = string.utf8len(data.nickname)
			for i = 1, charCount do
				name = string.utf8sub(data.nickname, 1, i)
				self.TestText.text = name
				if self.TestText.preferredWidth > 130 then
					name = name .. "..."
					break
				end 
			end
		end
	end

 	local text = self:find("Root/Text", item)
	bee.setText(text, _F("LAB_FESTIVAL_ACTIVITY1_1", "<color=#F7C169>" .. name .. "</color>", ""))
	CS.Utils.ForceRebuildLayoutImmediate(text)

	local rewardData = data.item_list[1]
	local itemCfg = tpl_props[rewardData.item_id]
	local icon = self:find("Root/Icon", item)
	icon:SetActive(true)
	bee.setIcon(icon, itemCfg.icon)
	local count = self:find("Root/Icon/Value", item)
	bee.setText(count, string.format("X %s", _N(rewardData.num)))
end

function P:loopEvent()
	self.RecordScrollContent.anchoredPosition = bee.v2(self.RecordScrollContent.anchoredPosition.x, self.RecordScrollContent.anchoredPosition.y + 1)
	if self.RecordScrollContent.anchoredPosition.y > self.limitHeight then
		self.RecordScrollContent.anchoredPosition = bee.v2(self.RecordScrollContent.anchoredPosition.x, self.RecordScrollContent.anchoredPosition.y - self.limitHeight + 46 * 2)
	end
end

function P:evt_ColorGameActionRSP()
	self:once(0.5, function()
		SpringFestivalModel:reqTaskList()
	end)
end

function P:evt_ItemChangeRSP(msg)
	SpringFestivalModel:refreshReddot()
end

function P:changeTip()
	local remainCount = table.nums(self.tipRandomCfg)
	if remainCount == 0 then
		for _,v in pairs(self.tipCfg) do
			table.insert(self.tipRandomCfg, v)
		end
		remainCount = table.nums(self.tipRandomCfg)
	end

	local cacheIndex = math.random(1, remainCount)
	local cfg = self.tipRandomCfg[cacheIndex]
	table.remove(self.tipRandomCfg, cacheIndex)
	local tip = _F("LAB_FESTIVAL_ACTIVITY1_6", cfg.publicity_pr, _T(tpl_props[cfg.rewards[1]].name), _N(cfg.rewards[2]))
	bee.setText(self.RedPacketTipText, tip)
end

