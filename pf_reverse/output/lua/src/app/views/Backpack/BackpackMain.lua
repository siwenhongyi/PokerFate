local P = class("BackpackMain", UiFullView)

local TabType = {
	Prop = 1,
	Gift = 2,
	Awake = 3,
	CardBack = 5,
	CardTable = 6,
	Music = 7,
	LobbyScene = 14,
	Eff = 17
}

local DecorateCfg = {
	[GPropKind.LobbyScene] = tpl_hall_scene,
	[GPropKind.Table] = tpl_card_table,
	[GPropKind.AllInEff] = tpl_all_in_anim,
}

local ItemBgList = {
	[0] = "Backpack[backpack_detail_grid_01]",
	[1] = "Backpack[backpack_detail_grid_02]",
	[2] = "Backpack[backpack_detail_grid_03]",
	[3] = "Backpack[backpack_detail_grid_04]",
	[4] = "Backpack[backpack_detail_grid_05]",
	[5] = "Backpack[backpack_detail_grid_06]",
}

local RecycleDropDown = {
	[1] = {quality = 1, text = "LAB_BACKPACK_DES_34"},
	[2] = {quality = 2, text = "LAB_BACKPACK_DES_35"},
	[3] = {quality = 3, text = "LAB_BACKPACK_DES_36"},
	[4] = {quality = 0, text = "LAB_BACKPACK_DES_37"},
}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")

	local Left = self:find("Left", AnimRoot)
	self.TabToggleCont = self:find("ToggleScrollView/Viewport/Content/TabToggleCont", Left)
	self.TabToggle = self:find("TabToggle", self.TabToggleCont)
	self.SubTabToggleCont = self:find("SubTabToggleCont", Left)
	self.SubTabToggle = self:find("SubTabToggleCont/SubTabToggle", Left)
	self.TabToggle:SetActive(false)
	self.SubTabToggleCont:SetActive(false)
	self.SubTabToggle:SetActive(false)

	local LeftTop = self:find("LeftTop", AnimRoot)
	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		-- 检查是否有过期道具
		ItemModel:requestRefreshItem()
		ItemModel:removeRedTagByBackPackId(self._clickType)
		self:hideUI()
	end)

	self.Center = self:find("Center", AnimRoot)
	self.ItemScrollList = self:find("ItemScrollList", self.Center)
	self.ItemSubTypeScrollList = self:find("ItemSubTypeScrollList", self.Center)
	self.PropItem = self:find("PropItem", self.Center)
	self.PropTypeLine = self:find("PropTypeLine", self.Center)
	self.PropItemRow = self:find("PropItemRow", self.Center)
	self.PropItem:SetActive(false)
	self.PropTypeLine:SetActive(false)
	self.PropItemRow:SetActive(false)
	self.Blank = self:find("Blank", self.Center)
	self.TopOptionCont = self:find("TopOptionCont", self.Center)
	self.OwnText = self:find("OwnText", self.TopOptionCont)
	self.OnlyOwnToggle = self:find("OnlyOwnToggle", self.TopOptionCont)
	self.MultipleRecycleButton = self:find("MultipleRecycleButton", self.TopOptionCont)
	bee.setUncheck(self.OnlyOwnToggle)

	self.ItemRecycleScrollList = self:find("ItemRecycleScrollList", self.Center)
	self.RecyclePropItem = self:find("RecyclePropItem", self.Center)
	self.ItemRecycleScrollList:SetActive(false)
	self.RecyclePropItem:SetActive(false)
	self.RecycleBlank = self:find("RecycleBlank", self.ItemRecycleScrollList)
	self.QualityFilter = self:find("QualityFilter", self.ItemRecycleScrollList)
	self.FilterButton = self:find("FilterButton", self.QualityFilter)
	self.ArrowButton = self:find("ArrowButton", self.FilterButton)
	self.FilterText = self:find("FilterText", self.FilterButton)
	self.DropDown = self:find("DropDown", self.QualityFilter)
	self.FilterMask = self:find("FilterMask", self.DropDown)

	self.Right = self:find("Right", AnimRoot)
	self.ItemDetail = self:find("ItemDetail", self.Right)
	self.ItemCountText = self:find("ItemCountText", self.ItemDetail)
	self.DetailGridBg = self:find("DetailGridBg", self.ItemDetail)
	self.DetailImgBg = self:find("DetailImgBg", self.ItemDetail)
	self.DetailImg = self:find("DetailImg", self.DetailImgBg)
	self.ItemIcon = self:find("ItemIcon", self.ItemDetail)
	self.ItemNameText = self:find("ItemNameText", self.ItemDetail)
	self.PreviewButton = self:find("PreviewButton", self.ItemDetail)
	self.PreviewButtonView = self:find("backpack_icon_view", self.PreviewButton)
	self.PreviewButtonPlay = self:find("backpack_icon_play", self.PreviewButton)
	self.ItemDescText = self:find("DescTextCont/Viewport/Content/ItemDescText", self.ItemDetail)
	self.ItemButtonYellow = self:find("ItemButtonYellow", self.ItemDetail)
	self.ItemButtonBlue = self:find("ItemButtonBlue", self.ItemDetail)
	self.Limited = self:find("Limited", self.ItemDetail)
	self.TimeText = self:find("TimeText", self.ItemDetail)
	self.UsedTag = self:find("UsedTag", self.ItemDetail)
	self.GiftBtnCont = self:find("GiftBtnCont", self.ItemDetail)
	self.ItemButtonUse = self:find("ItemButtonUse", self.GiftBtnCont)
	self.ItemButtonRecycle = self:find("ItemButtonRecycle", self.GiftBtnCont)
	self.TimeText:SetActive(false)
	self.UsedTag:SetActive(false)
	self.PreviewButton:SetActive(false)

	self.RightTop = self:find("RightTop", AnimRoot)
	self.GiftCurrency = self:find("CurrencyColumn/GiftCurrency", self.RightTop)
	self.GiftCurrency:SetActive(false)

	self.Quantity = self:find("Quantity", self.ItemDetail)
	self.MinButton = self:find("MinButton", self.Quantity)
	self.MaxButton = self:find("MaxButton", self.Quantity)
	self.MinusButton = self:find("MinusButton", self.Quantity)
	self.PlusButton = self:find("PlusButton", self.Quantity)
	self.InputFieldCount = self:find("InputFieldCount", self.Quantity)

	bee.addClick(self.MinButton, function()
		self:onClickMinButton()
	end)
	bee.addClick(self.MaxButton, function()
		self:onClickMaxButton()
	end)
	bee.addClick(self.MinusButton, function()
		self:onClickMinusButton()
	end)
	bee.addClick(self.PlusButton, function()
		self:onClickPlusButton()
	end)

	self.InputFieldCount:GetComponent("InputField").onEndEdit:AddListener(function()
		self:changeInputFieldCount()
	end)

	self.RecycleDetail = self:find("RecycleDetail", self.Right)
	self.RecycleIcon = self:find("RecycleCount/RecycleIcon", self.RecycleDetail)
	self.RecycleCount = self:find("RecycleCount", self.RecycleDetail)
	self.RecycleCloseButton = self:find("RecycleCloseButton", self.RecycleDetail)
	self.SelectAllButton = self:find("SelectAllButton", self.RecycleDetail)
	self.SelectNoneButton = self:find("SelectNoneButton", self.RecycleDetail)
	self.ConfirmButton = self:find("ConfirmButton", self.RecycleDetail)
	self.ItemDetail:SetActive(false)
	self.RecycleDetail:SetActive(false)

	bee.addValueChanged(self.OnlyOwnToggle, function(isOn)
		self._isOnlyShowOwn = isOn
		Game:playSound("ui_button_disabled")
		self:setItemListShow()
	end)

	bee.addClick(self.PreviewButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPreviewButton()
	end)

	bee.addClick(self.MultipleRecycleButton, function()
		Game:playSound("ui_button_confirm")
		ItemModel:removeRedTagByBackPackId(2)
		self:setRecycleShow()
	end)
	bee.addClick(self.RecycleCloseButton, function()
		Game:playSound("ui_button_confirm")
		self:closeRecycleShow()
	end)
	bee.addClick(self.SelectAllButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickSelectAllButton()
	end)
	bee.addClick(self.SelectNoneButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickSelectNoneButton()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:onClickRecycleConfirmButtom()
	end)

	bee.addClick(self.ItemButtonRecycle, function()
		Game:playSound("ui_button_confirm")
		self:onClickItemButtonRecycle()
	end)
	bee.addClick(self.ItemButtonUse, function()
		Game:playSound("ui_button_confirm")
		self:onClickJump()
	end)

	-- 回收筛选按钮
	bee.addClick(self.FilterButton, function()
		self.DropDown:SetActive(true)
		self:find("Arrow", self.ArrowButton).transform.localEulerAngles = bee.v3(0, 0, 0)
	end)
	bee.addClick(self.ArrowButton, function()
		self.DropDown:SetActive(true)
		self:find("Arrow", self.ArrowButton).transform.localEulerAngles = bee.v3(0, 0, 0)
	end)
	bee.addClick(self.FilterMask, function()
		self.DropDown:SetActive(false)
		self:find("Arrow", self.ArrowButton).transform.localEulerAngles = bee.v3(0, 0, 180)
	end)
	for i = 1, 4 do
		local dropDownItem = self:find("DropDownItem" .. i .."/Item", self.DropDown)
		bee.addClick(dropDownItem, function()
			self:onClickDropDownItem(i)
		end)
	end
end

function P:onStart()
	if self._params and self._params.jump then
		local jumpCfg = self._params.jump
		if jumpCfg.select then
			local propCfg = tpl_props[jumpCfg.select]
			if propCfg then
				if propCfg.type == GPropKind.RandomBox or propCfg.type == GPropKind.OptionalBox then
					self._clickType = 2
					self._jumpTo = jumpCfg.select
				end
			end
		else
			self._clickType = jumpCfg.sub_page and tonumber(jumpCfg.sub_page[1])
		end
	end
	self._hideSubTypeRow = {}
	if not self._clickType then
		self._clickType = 1
	end
	
	self:initItemList()
	self:initItemSubPageList()
	self:setLeftToggleCont()
	self:setItemListShow()
	self:setItemDetailShow()

	self:initCurrency()
end

function P:initCurrency()
	local propCfg = tpl_props[GPropId.GiftFragment]
	bee.setIconInAtlas(self:find("ItemIcon", self.GiftCurrency), propCfg.icon)
	bee.setTextGold(self:find("CountText", self.GiftCurrency), _N(ItemModel:getItemNumById(GPropId.GiftFragment)))

	bee.removeAllClick(self.GiftCurrency)
	bee.addClick(self.GiftCurrency, function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(GPropId.GiftFragment, true), target = self:find("ItemIcon", self.GiftCurrency)})
	end, true)
end

function P:setLeftToggleCont()
	self._toggleIdList = {}
	self._subToggleIdList = {}

	for i, v in ipairs(tpl_backpack) do
		self:initToggleItem(v)
	end

	self:refreshToggle(self._toggleIdList, true)
	self:refreshToggle(self._subToggleIdList, true)
end

function P:logEventById(id)
	if id == 1 then
		bee.logEvent("backpack-item")
	elseif id == 2 then
		bee.logEvent("backpack-gift")
	elseif id == 3 then
		bee.logEvent("backpack-oath")
	elseif id == 4 then
		bee.logEvent("backpack-decoration")
	elseif id == 5 then
		bee.logEvent("backpack-decoration-cards")
	elseif id == 6 then
		bee.logEvent("backpack-decoration-table")
	elseif id == 7 then
		bee.logEvent("backpack-decoration-bgm")
	elseif id == 14 then
		bee.logEvent("backpack-decoration-lobby")
	end
end

function P:refreshToggle(toggleList, notify)
	for k, v in pairs(toggleList) do
		if v.id == self._clickType then
			if bee.isCheck(v.toggle) and toggleList == self._subToggleIdList then
				local Animroot = self:find("Animroot", v.toggle)
				Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_SubTabToggleCont_into")
			end
			bee.setCheck(v.toggle, notify)
		else
			bee.setUncheck(v.toggle)
		end
	end
end

function P:initToggleItem(data)
	if data.tab_type ~= 1 then
		return
	end

	local copyToggle = CU.GameObject.Instantiate(self.TabToggle)
	copyToggle.transform:SetParent(self.TabToggleCont.transform)
	copyToggle.transform.localPosition = bee.v3(0, 0, 0)
	copyToggle.transform.localScale = bee.v3(1, 1, 1)
	copyToggle:SetActive(true)

	table.insert(self._toggleIdList, {toggle = copyToggle, id = data.id})

	local Animroot = self:find("Animroot", copyToggle)
	local SelectedTab = self:find("backpack_tab_01", Animroot)
	local Arrow1 = self:find("backpack_icon_arrow_01", Animroot)
	local Arrow2 = self:find("backpack_icon_arrow_02", Animroot)
	local ToggleIcon = self:find("ToggleIcon", Animroot)
	local NameText = self:find("NameText", Animroot)

	if data.red_name then
		RedManager:bind(self:find("RedPoint", Animroot), RedTag[data.red_name])
	end

	bee.setText(NameText, _T(data.name))
	bee.setIconInAtlas(ToggleIcon, data.page_icon)

	local subToggleCont
	if data.sub_page and data.show_type == 1 then
		Arrow1:SetActive(true)
		Arrow2:SetActive(false)

		subToggleCont = self:initSubToggleCont(data.sub_page)
	else
		Arrow1:SetActive(false)
		Arrow2:SetActive(false)
	end

	bee.setToggleGroup(copyToggle, self.TabToggleCont)

	local isShowSubCont = false

	bee.removeValueChanged(copyToggle)
	bee.addValueChanged(copyToggle, function(isOn)
		if data.sub_page and data.show_type == 1 then
			Game:playSound("ui_tab_switch_1")
			if isOn then
				local isSelectedSubPage = false
				for k,v in pairs(data.sub_page) do
					if self._clickType == v then
						isSelectedSubPage = true
						break
					end
				end
				if not isSelectedSubPage then
					Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
					ItemModel:removeRedTagByBackPackId(self._clickType)
					self._clickType = data.sub_page[1]
					self._clickItemData = nil
					self:refreshToggle(self._subToggleIdList, true)
					self.ItemScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
					self.ItemSubTypeScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
					self:setItemListShow()
					self:setItemDetailShow()
					if self._isInRecycle then
						self:closeRecycleShow()
					end
				end
			end
			if isOn then
				isShowSubCont = not isShowSubCont
			else
				isShowSubCont = false
				Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_idle2")
			end
			subToggleCont:SetActive(isShowSubCont)
			Arrow1:SetActive(not isShowSubCont)
			Arrow2:SetActive(isShowSubCont)
			if isShowSubCont then
				self:refreshSubToggle(subToggleCont)
			end
		else
			if isOn then
				if self._clickType ~= data.id then
					Game:playSound("ui_tab_switch_1")
					Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
					ItemModel:removeRedTagByBackPackId(self._clickType)
					self._clickType = data.id
					self._clickItemData = nil
					self.ItemScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
					self.ItemSubTypeScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
					self:setItemListShow()
					self:setItemDetailShow()
					if self._isInRecycle then
						self:closeRecycleShow()
					end
				end
			else
				Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_idle2")
			end
		end
		if isOn then
			self:logEventById(data.id)
			-- Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
		else
			-- Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_idle2")
		end
	end)

	if self._clickType == data.id then
		Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
	end
end

function P:initSubToggleCont(ids, toggle)
	local subToggleCont = CU.GameObject.Instantiate(self.SubTabToggleCont)
	subToggleCont.transform:SetParent(self.TabToggleCont.transform)
	subToggleCont.transform.localPosition = bee.v3(0, 0, 0)
	subToggleCont.transform.localScale = bee.v3(1, 1, 1)

	for i, v in ipairs(ids) do
		self:initSubToggle(v, subToggleCont, toggle)
	end

	return subToggleCont
end

function P:initSubToggle(id, parent, toggle)
	local data = tpl_backpack_list[id]
	if not data then
		return
	end

	local copySubToggle = CU.GameObject.Instantiate(self.SubTabToggle)
	copySubToggle.transform:SetParent(parent.transform)
	copySubToggle.transform.localPosition = bee.v3(0, 0, 0)
	copySubToggle.transform.localScale = bee.v3(1, 1, 1)
	copySubToggle:SetActive(true)

	table.insert(self._subToggleIdList, {toggle = copySubToggle, id = data.id})

	local Animroot = self:find("Animroot", copySubToggle)
	local SelectedTab = self:find("Animroot/backpack_tab_02", copySubToggle)
	local SelectedNameText = self:find("Animroot/NameText", SelectedTab)
	local NameText = self:find("Animroot/NameText", copySubToggle)
	bee.setText(NameText, _T(data.name))
	bee.setText(SelectedNameText, _T(data.name))

	bee.setToggleGroup(copySubToggle, parent)

	RedManager:unbind(self:find("RedPoint", Animroot))
	if data.red_name then
		RedManager:bind(self:find("RedPoint", Animroot), RedTag[data.red_name])
	end

	bee.removeValueChanged(copySubToggle)
	bee.addValueChanged(copySubToggle, function(isOn)
		if isOn then
			SelectedTab:SetActive(true)
			bee.setCheck(toggle)
			if self._clickType ~= data.id then
				Game:playSound("ui_tab_switch_2")
				Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_SubTabToggleCont_into")
				ItemModel:removeRedTagByBackPackId(self._clickType)
				self._clickType = data.id
				self._clickItemData = nil
				self.ItemScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
				self.ItemSubTypeScrollList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
				self:setItemListShow()
				self:setItemDetailShow()
				if self._isInRecycle then
					self:closeRecycleShow()
				end
			end
		else
			-- SelectedTab:SetActive(false)
			Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_SubTabToggleCont_idle2")
		end

		if isOn then
			self:logEventById(data.id)
			-- Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_SubTabToggleCont_into")
		else
			-- Animroot:GetComponent("Animator"):Play("UI_1_BackpackMain_SubTabToggleCont_idle2")
		end
		ItemModel:refreshReddot()
	end)
end

function P:refreshSubToggle(subToggleCont)
	if bee.isNull(subToggleCont) then
		return
	end
	for i = 1, subToggleCont.transform.childCount do
		local toggle = subToggleCont.transform:GetChild(i - 1):GetComponent("Toggle")
		local anim = self:find("Animroot", subToggleCont.transform:GetChild(i - 1)):GetComponent("Animator")
		if toggle.isOn then
			anim:Play("UI_1_BackpackMain_SubTabToggleCont_into")
		else
			anim:Play("UI_1_BackpackMain_SubTabToggleCont_idle2")
		end
	end
end

-- 初始化中间道具栏
local ROW_COUNT = 5
function P:initItemList()
	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 90)
		else
			table.insert(rowPos, 180 * i - 90)
		end
	end

	self.itemList = UiListEx:create(self.ItemScrollList)
	self.itemList:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.PropItem)
		item.gameObject:SetActive(true)
		return item
	end)
	self.itemList:setRefreshFunc(function(data, item)
		self:setPropItemShow(item, data)
	end)
	self.itemList:setRowCount(ROW_COUNT)
	self.itemList:setRowPostions(rowPos)
	self.itemList:setWidth(200)
end

function P:initItemSubPageList()
	self.itemSubPageList = UiListEx:create(self.ItemSubTypeScrollList)
	self.itemSubPageList:setCreateFunc(function(data)
		local item
		if data.__kind == 1 then		-- 类型分类线
			item = CU.GameObject.Instantiate(self.PropTypeLine)
		else
			item = CU.GameObject.Instantiate(self.PropItemRow)
		end
		item:SetActive(true)
		return item
	end)
	self.itemSubPageList:setRefreshFunc(function(data, item)
		if data.__kind == 1 then
			self:setPropTypeLineItem(item, data)
		else
			self:setPropItemRow(item, data)
		end
	end)
	self.itemSubPageList:setWidth({
		[1] = 56,
		[2] = 190,
	})
end

function P:setItemListShow()
	if self._isInRecycle then
		return
	end
	if tpl_backpack[self._clickType].sub_page then
		self.ItemScrollList:SetActive(false)
		self.ItemSubTypeScrollList:SetActive(true)

		self:showSubPageList(true)
	else
		self.ItemScrollList:SetActive(true)
		self.ItemSubTypeScrollList:SetActive(false)

		self:showNormalItemList()
	end

	self.TopOptionCont:SetActive(true)
	self.GiftCurrency:SetActive(false)
	if self._clickType == TabType.Prop then
		self.OwnText:SetActive(false)
		self.OnlyOwnToggle:SetActive(false)
		self.MultipleRecycleButton:SetActive(false)
	elseif self._clickType == TabType.Gift then
		self.OwnText:SetActive(false)
		self.OnlyOwnToggle:SetActive(true)
		self.GiftCurrency:SetActive(true)
		self:checkGiftGuide()
	elseif self._clickType == TabType.Music or self._clickType == TabType.Eff then
		self.OwnText:SetActive(false)
		self.OnlyOwnToggle:SetActive(true)
		self.MultipleRecycleButton:SetActive(false)
	elseif self._clickType == TabType.Awake then
		self.OwnText:SetActive(false)
		self.OnlyOwnToggle:SetActive(false)
		self.MultipleRecycleButton:SetActive(false)
	else
		self.OwnText:SetActive(true)
		self.OnlyOwnToggle:SetActive(true)
		self.MultipleRecycleButton:SetActive(false)
		
		local propType = tpl_backpack[self._clickType].props_type[1]
		local ownCount, totalCount = ItemModel:getPropTypeCount(propType)
		if not self._isOnlyShowOwn then
			bee.setText(self.OwnText, _T("LAB_BACKPACK_DES_22") .. ownCount .. "/" .. totalCount)
		else
			bee.setText(self.OwnText, _T("LAB_BACKPACK_DES_22") .. ownCount .. "/" .. ownCount)
		end

		self:decorationGuide()
	end
end

function P:showNormalItemList()
	self.itemList:clear()
	self.itemSubPageList:clear()

	local list
	if self._clickType == TabType.Prop then
		list = ItemModel:getPropItems()
	else
		list = ItemModel:getAllShowItems(self._clickType, self._isOnlyShowOwn)
	end
	self.itemDatas = list

	-- 点击页签时自动选中正在使用的装饰
	if not self._clickItemData and list and next(list) then
		if self._jumpTo then
			for k,v in pairs(list) do
				if v.cfg.id == self._jumpTo then
					self._clickItemData = v
					self._jumpTo = nil
					break
				end
			end
		else
			self._clickItemData = list[1]
			local curDisplay = self:_getCurDisplay(list[1].cfg.type)
			for k, v in pairs(list) do
				if self:_isInUse(v.cfg) then
					self._clickItemData = v
					break
				end
			end
		end
	end

	self.itemList:setDatas(list)

	if not next(list) then
		self.Blank:SetActive(true)
		self.ItemDetail:SetActive(false)
		self.Right:SetActive(false)
	else
		self.Blank:SetActive(false)
		self.ItemDetail:SetActive(true)
		self.Right:SetActive(true)
	end
end

function P:showSubPageList()
	self.itemList:clear()
	self.itemSubPageList:clear()

	local subPage = tpl_backpack[self._clickType].sub_page
	local list = {}
	local firstItemData
	self.itemSubDatas = {}
	
	local totalCount = 0
	for i, v in ipairs(subPage) do
		table.insert(list, {__kind = 1, propType = v})

		if not self._hideSubTypeRow[v] then
			local subList = ItemModel:getAllShowItems(v, self._isOnlyShowOwn)
			local subCount = #subList
			if subCount > 0 then
				self.itemSubDatas[subList[1].cfg.type] = {}
				for i = 1, #subList, ROW_COUNT do
					local rowItems = {}
					for j = i, i + ROW_COUNT do
						if subList[j] then
							table.insert(self.itemSubDatas[subList[1].cfg.type], subList[j])
							table.insert(rowItems, subList[j])
						else
							break
						end
					end
					table.insert(list, {__kind = 2, rowItems = rowItems})
				end
				totalCount = totalCount + subCount
			end

			if not firstItemData then
				firstItemData = subList[1]
			end
		end
	end

	if (totalCount == 0 and self._isOnlyShowOwn) or not next(list) then
		self.Blank:SetActive(true)
		self.ItemDetail:SetActive(false)
		self.Right:SetActive(false)
		self.ItemSubTypeScrollList:SetActive(false)
		self.MultipleRecycleButton:SetActive(false)
	else
		-- 点击页签时自动选中正在使用的装饰
		if not self._clickItemData and list then
			for k, v in pairs(list) do
				if v.rowItems then
					for k1, v1 in pairs(v.rowItems) do
						if self._jumpTo and v1.cfg.id == self._jumpTo then
							self._clickItemData = v1
							self._jumpTo = nil
							break
						elseif self:_isInUse(v1.cfg) then
							self._clickItemData = v1
							break
						end
					end
				end
				if self._clickItemData then
					break
				end
			end
			if not self._clickItemData then
				self._clickItemData = firstItemData
			end
		end

		self.itemSubPageList:setDatas(list)
		self.ItemSubTypeScrollList:SetActive(true)
		self.Blank:SetActive(false)
		-- self.ItemDetail:SetActive(true)
		self.Right:SetActive(true)
		self.MultipleRecycleButton:SetActive(self._clickType == TabType.Gift)
	end
end

-- 道具Item显示
function P:setPropItemShow(item, data)
	local PropItemObj = self:find("PropItem", item)
	local prop = PropItem:create(PropItemObj, data)

	local LockMask = self:find("LockMask", item)
	local LockIcon = self:find("LockIcon", item)
	local Decorate = self:find("Decorate", item)
	local Selected = self:find("Selected", PropItemObj)
	local NewIcon = self:find("NewIcon", item)

	local isSelected = self._clickItemData.item_id == data.item_id
	if self._clickItemData.item_uniq_id then
		isSelected = self._clickItemData.item_uniq_id == data.item_uniq_id
	end
	Selected:SetActive(isSelected)
	NewIcon:SetActive(ItemModel:isNewItem(data.item_id))
	if self._clickType == TabType.Prop then
		-- 普通道具
		LockMask:SetActive(false)
		LockIcon:SetActive(false)
		Decorate:SetActive(false)
	elseif self._clickType == TabType.Gift or self._clickType == TabType.Awake then
		-- 礼物/觉醒道具
		LockMask:SetActive(data.num <= 0)
		LockIcon:SetActive(data.num <= 0)
		Decorate:SetActive(false)
		if data.num <= 0 then
			prop:hideLinkTag()
		end
	else
		-- 装饰
		local lock = data.num <= 0
		if lock then
			LockMask:SetActive(true)
			LockIcon:SetActive(true)
			Decorate:SetActive(false)
		else
			LockMask:SetActive(false)
			LockIcon:SetActive(false)
			Decorate:SetActive(true)

			local isCurUsed = self:_isInUse(data.cfg)
			local MusicUsed = self:find("MusicUsed", Decorate)
			local Used = self:find("Used", Decorate)

			if isCurUsed then
				if data.cfg.type == GPropKind.MusicLobby or data.cfg.type == GPropKind.MusicTable then
					MusicUsed:SetActive(true)
					Used:SetActive(false)
				else
					MusicUsed:SetActive(false)
					Used:SetActive(true)
				end
			else
				MusicUsed:SetActive(false)
				Used:SetActive(false)
			end
		end
	end

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		Game:playSound("ui_button_confirm")
		if self._clickItemData == data then
			return
		end

		ItemModel:removeRedTagById(data.item_id)

		self._clickItemData = data
		self:setItemDetailShow()

		if tpl_backpack[self._clickType].sub_page then
			self.itemSubPageList:refreshShowingUi()
		else
			self.itemList:refreshShowingUi()
		end
	end)
end

function P:setPropTypeLineItem(item, data)
	local propType = data.propType
	local cfg = tpl_backpack[propType]

	local TitleText = self:find("TitleText", item)
	local OwnText = self:find("OwnText", item)
	local ArrowIcon = self:find("ArrowIcon", item)

	bee.setText(TitleText, _T(cfg.name))

	if self._clickType == TabType.Gift then
		OwnText:SetActive(false)
	else
		OwnText:SetActive(true)
		local ownCount, totalCount = ItemModel:getPropTypeCount(cfg.props_type[1])
		if not self._isOnlyShowOwn then
			bee.setText(OwnText, _T("LAB_BACKPACK_DES_22") .. ownCount .. "/" .. totalCount)
		else
			bee.setText(OwnText, _T("LAB_BACKPACK_DES_22") .. ownCount .. "/" .. ownCount)
		end
	end

	if self._hideSubTypeRow[propType] then
		bee.setUncheck(item)
		ArrowIcon.transform.eulerAngles = bee.v3(0, 0, -90)
	else
		bee.setCheck(item)
		ArrowIcon.transform.eulerAngles = bee.v3(0, 0, 0)
	end


	bee.removeValueChanged(item)
	bee.addValueChanged(item, function(isOn)
		if isOn then
			self._hideSubTypeRow[propType] = nil
		else
			self._hideSubTypeRow[propType] = 1
		end
		self:showSubPageList()
	end)
end

function P:setPropItemRow(item, data)
	for i = 1, 5 do
		local PropItem = self:find("PropItem" .. i, item)
		if data.rowItems[i] then
			PropItem:SetActive(true)
			self:setPropItemShow(PropItem, data.rowItems[i])
		else
			PropItem:SetActive(false)
		end
	end
end

function P:setItemDetailShow()
	if self._isInRecycle then
		return
	end
	if not self._clickItemData then
		return
	end

	self.UsedTag:SetActive(false)
	self.Quantity:SetActive(false)
	self.TimeText:SetActive(false)

	local propCfg = self._clickItemData.cfg
	bee.setText(self.ItemNameText, _T(propCfg.name))
	bee.setText(self.ItemDescText, ItemModel:getItemDesText(propCfg.id))

	if tpl_backpack[self._clickType].show_num then
		self.ItemCountText:SetActive(true)
		bee.setText(self.ItemCountText, "x" .. self._clickItemData.num)
	else
		self.ItemCountText:SetActive(false)
	end

	if DecorateCfg[propCfg.type] then
		self.DetailGridBg:SetActive(false)
		self.DetailImgBg:SetActive(true)
		self.ItemIcon:SetActive(false)
		local decCfg = DecorateCfg[propCfg.type][propCfg.mapId]
		bee.setIconInAtlas(self.DetailImg, decCfg.bg_small, true)
	elseif propCfg.type == GPropKind.NameplateEff then
		self.DetailGridBg:SetActive(true)
		self.DetailImgBg:SetActive(false)
		self.ItemIcon:SetActive(true)
		self.ItemIcon.transform.localScale = bee.v3(1, 1, 1)
		local decCfg = tpl_nameplate_anim[propCfg.mapId]
		bee.setIconInAtlas(self.ItemIcon, propCfg.icon, true)
		bee.setIconInAtlas(self.DetailGridBg, ItemBgList[propCfg.quality])
	else
		self.DetailGridBg:SetActive(true)
		self.DetailImgBg:SetActive(false)
		self.ItemIcon:SetActive(true)
		self.ItemIcon.transform.localScale = bee.v3(0.7, 0.7, 1)
		bee.setIconInAtlas(self.ItemIcon, propCfg.icon, true)
		bee.setIconInAtlas(self.DetailGridBg, ItemBgList[propCfg.quality])
	end

	if self._clickType == TabType.Prop then
		self:setNormalPropDetailShow()
	elseif self._clickType == TabType.Gift then
		self:setGiftPropDetailShow()
	elseif self._clickType == TabType.Awake then
		self:setAwakePropDetailShow()
	else
		self:setDisplayPropDetailShow()
	end
end

-- 道具页签的道具按钮显示
function P:setNormalPropDetailShow()
	if not self._clickItemData then
		return
	end

	self.ItemDetail:SetActive(true)

	local cfg = self._clickItemData.cfg

	self.PreviewButton:SetActive(cfg.preview == 1)
	self.Quantity:SetActive(false)

	if cfg.type == GPropKind.Box or cfg.type == GPropKind.RandomBox then
		self:setBathchBox()
	elseif cfg.type == GPropKind.OptionalBox then
		self:setButtonUseTreasureBox()
	elseif cfg.type == GPropKind.ExpCard then
		self:setButtonUseExpCard()
	elseif cfg.jump then
		self:setButtonJump(cfg.jump)
	elseif cfg.accesses then
		self:setButtonAccess()
	else
		self:setAccessText()
	end

	self:setItemDetailTimeText()
end

function P:setBathchBox()
	local cfg = self._clickItemData.cfg
	local count = ItemModel:getItemNumById(cfg.id)
	if count <= 0 then
		self:setButtonAccess()
		return
	end

	self._batchSelectCount = 1
	if cfg.batchUse == 1 then
		self.Quantity:SetActive(true)
		self._batchMaxCount = count
		self:setInputFieldCount()
	else
		self.Quantity:SetActive(false)
	end

	bee.setText(self:find("Text", self.ItemButtonYellow), _T("LAB_BACKPACK_DES_16"))
	self:setButtonUseTreasureBox()
end

function P:onClickMinButton()
	if self._batchSelectCount <= 1 then
		UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
		return
	end
	Game:playSound("ui_button_confirm")
	self._batchSelectCount = 1
	self:setInputFieldCount()
end

function P:onClickMaxButton()
	if self._batchSelectCount >= self._batchMaxCount then
		UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
		return
	end
	Game:playSound("ui_button_confirm")
	self._batchSelectCount = self._batchMaxCount
	self:setInputFieldCount()
end

function P:onClickMinusButton()
	if self._batchSelectCount <= 1 then
		UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
		return
	end
	Game:playSound("ui_button_confirm")
	self._batchSelectCount = math.max(1, self._batchSelectCount - 1)
	self:setInputFieldCount()
end

function P:onClickPlusButton()
	if self._batchSelectCount >= self._batchMaxCount then
		UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
		return
	end
	Game:playSound("ui_button_confirm")
	self._batchSelectCount = math.min(self._batchMaxCount, self._batchSelectCount + 1)
	self:setInputFieldCount()
end

function P:changeInputFieldCount()
	local inputCount = tonumber(bee.getText(self.InputFieldCount, "InputField"))
	if not inputCount then
		self:setInputFieldCount()
		return
	end
	if inputCount < 1 then
		inputCount = 1
	end
	if inputCount > self._batchMaxCount then
		inputCount = self._batchMaxCount
	end
	
	self._batchSelectCount = inputCount
	self:setInputFieldCount()
end

function P:setInputFieldCount()
	bee.setText(self.InputFieldCount, self._batchSelectCount, "InputField")
end

function P:setItemDetailTimeText()
	if self._timeCountDown then
		scheduler:removeTag(self._timeCountDown)
		self._timeCountDown = nil
	end

	local cfg = tpl_props[self._clickItemData.item_id]
	if not cfg.duration and not cfg.expirationTime then
		self.TimeText:SetActive(false)
		return
	end

	local deadline = self._clickItemData.deadline
	if not deadline then
		self.TimeText:SetActive(false)
		return
	end

	self.TimeText:SetActive(true)

	local dt = deadline - bee.getServerTime()
	if dt <= 0 then
		bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
		return
	end

	bee.setText(self.TimeText, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(dt)))
	self._timeCountDown = self:schedule(1, function()
		dt = dt - 1
		if dt > 0 then
			bee.setText(self.TimeText, _F("LAB_TIME_DES", ItemModel:getPropItemTimeStr(dt)))
		else
			bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
			scheduler:removeTag(self._timeCountDown)
			self._timeCountDown = nil
		end
	end)
end

function P:setGiftPropDetailShow()
	if not self._clickItemData then
		return
	end

	self.ItemDetail:SetActive(true)

	local cfg = self._clickItemData.cfg
	self.PreviewButton:SetActive(cfg.preview == 1)
	self.TimeText:SetActive(false)

	if cfg.type == GPropKind.Box or cfg.type == GPropKind.RandomBox then
		self:setBathchBox()
	elseif cfg.type == GPropKind.OptionalBox then
		self:setButtonUseTreasureBox()
	else
		self.TimeText:SetActive(false)

		local num = ItemModel:getItemNumById(cfg.id)
		if num > 0 and cfg.isBinding ~= 1 then
			-- 已拥有礼物，显示跳转使用/回收
			self:setGiftButtonCont()
		elseif num > 0 then
			self:setButtonJump(cfg.jump)
		elseif cfg.accesses then
			self:setButtonAccess()
		else
			self:setAccessText()
		end
	end
end

function P:setAwakePropDetailShow()
	if not self._clickItemData then
		return
	end

	self.ItemDetail:SetActive(true)

	local cfg = self._clickItemData.cfg

	self.PreviewButton:SetActive(cfg.preview == 1)
	self.TimeText:SetActive(false)

	if self._clickItemData.num > 0 then
		-- 已拥有礼物，显示跳转使用
		self:setButtonJump(cfg.jump)
	elseif cfg.accesses then
		self:setButtonAccess()
	else
		self:setAccessText()
	end
end

function P:_getCurDisplay(checkType)
	local curDisplay
	if checkType == GPropKind.CardBack then
		curDisplay = PlayerModel:getCurCardBack()
	elseif checkType == GPropKind.Table then
		curDisplay = PlayerModel:getCurCardTable()
	elseif checkType == GPropKind.MusicLobby then
		curDisplay = PlayerModel:getCurMusicLobby()
	elseif checkType == GPropKind.MusicTable then
		curDisplay = PlayerModel:getCurMusicBattle()
	elseif checkType == GPropKind.LobbyScene then
		curDisplay = PlayerModel:getCurLobbyScene()
	elseif checkType == GPropKind.AllInEff then
		curDisplay = PlayerModel:getCurAllInEff()
	elseif checkType == GPropKind.NameplateEff then
		curDisplay = PlayerModel:getCurNameplateEff()
	elseif checkType == GPropKind.CardFace then
		curDisplay = PlayerModel:getCurCardFace()
	end

	return curDisplay
end

function P:_isInUse(cfg)
	local curDisplay = self:_getCurDisplay(cfg.type)
	if not curDisplay then
		return false
	end

	local isIn = false
	if cfg.type == GPropKind.MusicLobby then
		for k,v in pairs(curDisplay) do
			if v == tpl_props[cfg.id].mapId then
				isIn = true
				break
			end
		end
	else
		isIn = tpl_props[cfg.id].mapId == curDisplay
	end
	return isIn
end

-- 使用经验卡
function P:setButtonUseExpCard()
	self.ItemButtonYellow:SetActive(true)
	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)

	local cfg = self._clickItemData.cfg
	self._batchSelectCount = 1
	self.Quantity:SetActive(true)
	self._batchMaxCount = ItemModel:getItemNumById(cfg.id)
	self:setInputFieldCount()

	bee.setText(self:find("Text", self.ItemButtonYellow), _T("LAB_BACKPACK_DES_16"))

	bee.removeAllClick(self.ItemButtonYellow)
	bee.addClick(self.ItemButtonYellow, function()
		ItemModel:requestUseExpCard(self._clickItemData.item_uniq_id, self._batchSelectCount)
	end)
end

function P:setDisplayPropDetailShow()
	local cfg = self._clickItemData.cfg

	self.PreviewButton:SetActive(cfg.preview == 1)
	if cfg.type == GPropKind.MusicLobby or cfg.type == GPropKind.MusicTable then
		self.PreviewButtonPlay:SetActive(true)
		self.PreviewButtonView:SetActive(false)
	else
		self.PreviewButtonPlay:SetActive(false)
		self.PreviewButtonView:SetActive(true)
	end

	if self:_isInUse(cfg) then
		self.UsedTag:SetActive(true)
		self:setButtonUsed()
	elseif ItemModel:getItemNumById(self._clickItemData.cfg.id) > 0 then
		self:setButtonUse()
	elseif cfg.accesses then
		self:setButtonAccess()
	else
		self:setAccessText()
	end
end

-- 跳转使用按钮
function P:setButtonJump(jump)
	self.ItemButtonYellow:SetActive(true)
	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)

	local jumpCfg = tpl_Jump_path[jump]
	if jumpCfg then
		bee.setText(self:find("Text", self.ItemButtonYellow), _T(jumpCfg.use_button_text))
	else
		self.ItemButtonYellow:SetActive(false)
	end

	bee.removeAllClick(self.ItemButtonYellow)
	bee.addClick(self.ItemButtonYellow, function()
		Game:playSound("ui_button_confirm")
		self:onClickJump()
	end)
end

-- 前往获得按钮
function P:setButtonAccess()
	-- 判断是否有可跳转的途径
	local accesses = self._clickItemData.cfg.accesses
	if not ItemModel:isCanJump(accesses, self._clickItemData.cfg.id) then
		self:setAccessText()
		return
	end

	self.ItemButtonYellow:SetActive(false)
	self.ItemButtonBlue:SetActive(true)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)

	bee.setText(self:find("Text", self.ItemButtonBlue), _T("LAB_PROPS_TEXT_3"))

	bee.removeAllClick(self.ItemButtonBlue)
	bee.addClick(self.ItemButtonBlue, function()
		Game:playSound("ui_button_confirm")
		self:onClickApproach()
	end)
end

function P:setGiftButtonCont()
	self.ItemButtonYellow:SetActive(false)
	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(true)

	local jumpCfg = tpl_Jump_path[self._clickItemData.cfg.jump]
	bee.setText(self:find("Text", self.ItemButtonUse), _T(jumpCfg.use_button_text))
end

function P:onClickItemButtonRecycle()
	UiManager:showUI("BackpackRecycle", {data = self._clickItemData})
end

-- 装饰使用按钮
function P:setButtonUse()
	self.ItemButtonYellow:SetActive(true)
	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)

	bee.setText(self:find("Text", self.ItemButtonYellow), _T("LAB_BACKPACK_DES_16"))

	bee.removeAllClick(self.ItemButtonYellow)
	bee.addClick(self.ItemButtonYellow, function()
		if self._clickItemData.cfg.type == GPropKind.MusicLobby then
			PlayerModel:useLobbyBgm(self._clickItemData.cfg.id)
		elseif self._clickItemData.cfg.type == GPropKind.LobbyScene then
			PlayerModel:useLobbyScene(self._clickItemData.cfg.id)
		elseif self._clickItemData.cfg.type == GPropKind.AllInEff or self._clickItemData.cfg.type == GPropKind.NameplateEff 
			or self._clickItemData.cfg.type == GPropKind.CardFace  then
			ItemModel:reqChangeAnimation(self._clickItemData)
		else
			ItemModel:reqUseItem(self._clickItemData)
		end
		UiManager:showToast(_T("LAB_BACKPACK_TIPS_3"))
	end)
end

-- 使用中按钮
function P:setButtonUsed()
	self.ItemButtonYellow:SetActive(false)
	self.ItemButtonBlue:SetActive(true)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)

	bee.setText(self:find("Text", self.ItemButtonBlue), _T("LAB_BACKPACK_DES_14"))

	bee.removeAllClick(self.ItemButtonBlue)
	bee.addClick(self.ItemButtonBlue, function()
		UiManager:showToast(_T("LAB_BACKPACK_DES_18"))
	end)
end

-- 开宝箱按钮
function P:setButtonUseTreasureBox()
	local cfg = self._clickItemData.cfg
	local count = ItemModel:getItemNumById(cfg.id)

	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(false)
	self.GiftBtnCont:SetActive(false)
	if count <= 0 then
		self:setButtonAccess()
		return
	end
	self.ItemButtonYellow:SetActive(true)

	bee.setText(self:find("Text", self.ItemButtonYellow), _T("LAB_BACKPACK_DES_16"))

	bee.removeAllClick(self.ItemButtonYellow)
	bee.addClick(self.ItemButtonYellow, function()
		local cfg = self._clickItemData.cfg
		if cfg.type == GPropKind.Box or cfg.type == GPropKind.RandomBox then
			ItemModel:reqUseTreasureBox(self._clickItemData.item_uniq_id, self._batchSelectCount)
		elseif cfg.type == GPropKind.OptionalBox then
			Game:playSound("ui_button_confirm")
			UiManager:showUI("BackpackGift", {id = cfg.id})
		end

		ItemModel:removeRedTagById(cfg.id)
		if tpl_backpack[self._clickType].sub_page then
			self.itemSubPageList:refreshShowingUi()
		else
			self.itemList:refreshShowingUi()
		end
	end)
end

-- 限时活动提示
function P:setAccessText()
	self.ItemButtonYellow:SetActive(false)
	self.ItemButtonBlue:SetActive(false)
	self.Limited:SetActive(true)
end

function P:onClickJump()
	-- 判断是否过期
	if self._clickItemData.deadline and self._clickItemData.deadline > 0 and self._clickItemData.deadline < bee.getServerTime() then
		UiManager:showToast(_T("LAB_BACKPACK_DES_20"))
		ItemModel:requestRefreshItem()
		self:setItemListShow()
		self:setItemDetailShow()
		return
	end

	-- 跳转
	local propCfg = tpl_props[self._clickItemData.item_id]
	ItemModel:jumpView(propCfg.jump, self._clickItemData.cfg.id)
end

function P:onClickApproach()
	UiManager:showUI("BackpackDetail", {data = self._clickItemData})
end

function P:onClickPreviewButton()
	-- 任务进度-背包预览装饰
	TaskModel:reportTask(TaskType.PreviewDirection)
	
	if self._clickItemData.cfg.type == GPropKind.CardBack or self._clickItemData.cfg.type == GPropKind.CardFace
		or self._clickItemData.cfg.type == GPropKind.Table or self._clickItemData.cfg.type == GPropKind.NameplateEff then
		UiManager:showUI("BackpackPreview", {data = self._clickItemData})
	elseif self._clickItemData.cfg.type == GPropKind.AllInEff then
		local themeInfo = PlayerModel:getCurScheme()
		local skinCfg = tpl_character_skin[themeInfo.skin_id]
		UiManager:showUI(GameModel:getAllinUiName(self._clickItemData.cfg.id), {role = CharacterModel:getRoleData(skinCfg.role), skin = skinCfg})
	elseif self._clickItemData.cfg.type == GPropKind.MusicLobby or self._clickItemData.cfg.type == GPropKind.MusicTable then
		UiManager:showUI("BackpackMusic", {data = self._clickItemData, list = self.itemSubDatas[self._clickItemData.cfg.type], cb = function(data)
			if data ~= self._clickItemData then
				self._clickItemData = data
				self:setItemDetailShow()
				self.itemSubPageList:refreshShowingUi()
			end
		end})
	elseif self._clickItemData.cfg.type == GPropKind.LobbyScene then
		UiManager:showUI("BackpackLobbyPreview", {data = self._clickItemData, list = self.itemDatas, cb = function(data)
			if data ~= self._clickItemData then
				self._clickItemData = data
				self:setItemListShow()
				self:setItemDetailShow()
			end
		end})
	end
	bee.logEvent("backpack-preview", self._clickItemData.cfg.id)
end

-- ===================== 回收 =====================

function P:refreshRecycleList()
	self._recycleList = ItemModel:getRecycleList(self._clickType, RecycleDropDown[self._recycleFilter].quality)
end

function P:setRecycleShow()
	self._recycleFilter = 4
	self:refreshRecycleList()
	if not self._recycleList or not next(self._recycleList) then
		UiManager:showToast(_T("LAB_BACKPACK_DES_23"))
		return
	end

	self._isInRecycle = true
	if recycleList then
		self._selectedRecycleList = recycleList
	else
		self._selectedRecycleList = {}
	end
	bee.setText(self.FilterText, _T(RecycleDropDown[self._recycleFilter].text))

	self.Blank:SetActive(false)
	self.ItemDetail:SetActive(false)
	self.TopOptionCont:SetActive(false)
	self.RecycleDetail:SetActive(true)

	self.ItemScrollList:SetActive(false)
	self.ItemSubTypeScrollList:SetActive(false)
	self.ItemRecycleScrollList:SetActive(true)

	self.RecycleBlank:SetActive(false)
	self.DropDown:SetActive(false)

	self:setRecycleItemListShow(list)
	self:refreshRecycleDetail()

	self:recyclingGuide()
end

function P:closeRecycleShow()
	self._isInRecycle = false
	self._selectedRecycleList = {}

	self.RecycleDetail:SetActive(false)
	self.ItemDetail:SetActive(true)

	self.ItemRecycleScrollList:SetActive(false)
	self:setItemListShow()
	self:setItemDetailShow()
end

function P:onClickDropDownItem(index)
	self.DropDown:SetActive(false)
	if index == self._recycleFilter then
		return
	end

	self._recycleFilter = index
	self:find("Arrow", self.ArrowButton).transform.localEulerAngles = bee.v3(0, 0, 180)
	bee.setText(self.FilterText, _T(RecycleDropDown[self._recycleFilter].text))

	self:refreshRecycleList()
	for uniq_id, v in pairs(self._selectedRecycleList) do
		local isIn
		for _, v1 in pairs(self._recycleList) do
			if uniq_id == v1.item_uniq_id then
				isIn = true
				break
			end
		end
		if not isIn then
			self._selectedRecycleList[uniq_id] = 0
		end
	end

	self:setRecycleItemListShow()
	self:refreshRecycleDetail()
end

function P:initRecycleItemList()
	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 90)
		else
			table.insert(rowPos, 180 * i - 90)
		end
	end

	self.recycleItemList = UiListEx:create(self.ItemRecycleScrollList)
	self.recycleItemList:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.RecyclePropItem)
		item.gameObject:SetActive(true)
		return item
	end)
	self.recycleItemList:setRefreshFunc(function(data, item)
		self:setRecyclePropItemShow(item, data)
	end)
	self.recycleItemList:setRowCount(ROW_COUNT)
	self.recycleItemList:setRowPostions(rowPos)
	self.recycleItemList:setWidth(200)
end

function P:setRecycleItemListShow()
	if not self.recycleItemList then
		self:initRecycleItemList()
	end
	self.recycleItemList:setDatas(self._recycleList)
end

function P:setRecyclePropItemShow(item, data)
	local PropItem = self:find("PropItem", item)
	bee.emitTo(PropItem, "init", data)

	local Selected = self:find("Selected", item)
	Selected:SetActive(self._selectedRecycleList[data.item_uniq_id] and self._selectedRecycleList[data.item_uniq_id] > 0)

	bee.removeAllClick(item)
	bee.addClick(item, function()
		Game:playSound("ui_button_confirm")
		if not self._selectedRecycleList[data.item_uniq_id] then
			self._selectedRecycleList[data.item_uniq_id] = 0
		end
		if self._selectedRecycleList[data.item_uniq_id] > 0 then
			self._selectedRecycleList[data.item_uniq_id] = 0
		else
			self._selectedRecycleList[data.item_uniq_id] = data.num
		end
		Selected:SetActive(self._selectedRecycleList[data.item_uniq_id] > 0)
		self:refreshRecycleDetail()
	end)
end

function P:refreshRecycleDetail()
	local recycleId
	local recycleCount = 0
	local allSelected = true
	if not next(self._selectedRecycleList) then
		allSelected = false
	else
		for k, v in pairs(self._selectedRecycleList) do
			local decProps = tpl_props[ItemModel:getItemById(k).item_id].decProps
			recycleCount = recycleCount + decProps[2] * v
			recycleId = decProps[1]
		end

		if allSelected then
			for k, v in pairs(self._recycleList) do
				if not self._selectedRecycleList[v.item_uniq_id] then
					allSelected = false
					break
				elseif self._selectedRecycleList[v.item_uniq_id] <= 0 then
					allSelected = false
					break
				end
			end
		end
	end

	bee.setIconInAtlas(self.RecycleIcon, tpl_props[tpl_constdata.GiftDecProps].icon, true)
	bee.setText(self.RecycleCount, "x" .. recycleCount)

	if allSelected  then
		self.SelectNoneButton:SetActive(true)
		self.SelectAllButton:SetActive(false)
	else
		self.SelectNoneButton:SetActive(false)
		self.SelectAllButton:SetActive(true)
	end

	if not next(self._recycleList) then
		self.RecycleBlank:SetActive(true)
	else
		self.RecycleBlank:SetActive(false)
	end
end

-- 全部选择
function P:onClickSelectAllButton()
	if not self._selectedRecycleList then
		self._selectedRecycleList = {}
	end
	for k, v in pairs(self._recycleList) do
		self._selectedRecycleList[v.item_uniq_id] = v.num
	end

	self:setRecycleItemListShow()
	self:refreshRecycleDetail()
end

-- 全部取消
function P:onClickSelectNoneButton()
	if not self._selectedRecycleList then
		self._selectedRecycleList = {}
	end
	for k,v in pairs(self._recycleList) do
		self._selectedRecycleList[v.item_uniq_id] = 0
	end

	self:setRecycleItemListShow()
	self:refreshRecycleDetail()
end

function P:onClickRecycleConfirmButtom()
	local params = {}
	params.req_item_list = {}

	local isEmpty = true
	for k,v in pairs(self._selectedRecycleList) do
		if v > 0 then
			table.insert(params.req_item_list, {item_uniq_id = k, item_num = v})
			isEmpty = false
		end
	end

	if isEmpty then
		UiManager:showToast(_T("LAB_BACKPACK_DES_12"))
		return
	end
	Game:playSound("ui_button_confirm")
	Net:sendReq("pb.RecycleItemREQ", params)
	bee.logEvent("backpack-recycle")
end

function P:evt_RecycleItemRSP(rewardList)
	-- 恭喜获得弹窗
	local items = {}
	if rewardList then
		for k, v in pairs(rewardList) do
			for k1, v1 in pairs(v) do
				table.insert(items, v1)
			end
		end
	end
	
	if next(items) then
		UiManager:showUI("BackpackClaimResult", {items = items})
	end

	if not self._isInRecycle then
		return
	end
	-- 刷新界面
	self:refreshRecycleList()
	self._selectedRecycleList = {}
	self:setRecycleItemListShow()
	self:refreshRecycleDetail()
end

function P:evt_ChangeOutFitsRSP(msg)
	self:setItemListShow()
	self:setItemDetailShow()
end

function P:evt_updateScheme()
	self:setItemListShow()
	self:setItemDetailShow()
end

function P:evt_ItemChangeRSP(msg)
	bee.setTextGold(self:find("CountText", self.GiftCurrency), _N(ItemModel:getItemNumById(GPropId.GiftFragment)))

	if (self._clickType == TabType.Prop or self._clickType == TabType.Gift) and self._clickItemData then
		if ItemModel:getItemNumById(self._clickItemData.cfg.id) <= 0 then
			self._clickItemData = nil
		end
	end

	if self._isInRecycle then
		return
	end
	self:setItemListShow()
	self:setItemDetailShow()
end

function P:evt_ChangeAnimationRSP()
	self:setItemListShow()
	self:setItemDetailShow()
end

function P:evt_BackpackClaimResultClose()
	self:setItemListShow()
	self:setItemDetailShow()
end

--引导

--背包礼物
function P:checkGiftGuide()
	GuideManager:startSystemGuide(2001, 0.65)
end
--批量回收
function P:recyclingGuide()
	GuideManager:startSystemGuide(3001, 0.65)
end
--装饰界面
function P:decorationGuide()
	GuideManager:startSystemGuide(4001, 0.65)
end

