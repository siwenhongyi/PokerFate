local P = class("BackpackRecycle", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)

	self.CloseButton = self:find("CloseButton", Center)
	self.ItemCont = self:find("ItemCont", Center)
	self.Own = self:find("Own", Center)
	self.PropItemObj = self:find("ItemCont/PropItem", Center)
	self.TitleText = self:find("TitleText", Center)
	self.DescText = self:find("DescCont/Viewport/Content/DescText", Center)

	self.RecycleItemButton = self:find("TextCont/ItemIcon/RecycleItemButton", Center)
	self.RecycleCountText = self:find("TextCont/RecycleCountText", Center)

	self.ItemButton = self:find("TextCont/ItemIcon/ItemButton", Center)
	self.RecycleCountText = self:find("TextCont/RecycleCountText", Center)
	self.InputFieldCount = self:find("InputFieldCount", Center)
	self.AddButton = self:find("AddButton", Center)
	self.AddTenButton = self:find("AddTenButton", Center)
	self.MaxButton = self:find("MaxButton", Center)
	self.MinusButton = self:find("MinusButton", Center)
	self.MinTenButton = self:find("MinTenButton", Center)
	self.MinButton = self:find("MinButton", Center)
	
	self.InputFieldCount:GetComponent("InputField").contentType = CU.UI.InputField.ContentType.IntegerNumber

	self.CancelButton = self:find("CancelButton", Center)
	self.RecycleButton = self:find("RecycleButton", Center)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.RecycleButton, function()
		self:onClickRecycle()
	end)
end

function P:onStart()
	local data = self._params.data
	self._cfg = data.cfg

	PropItem:create(self.PropItemObj, {item_id = self._cfg.id, num = 0})
	bee.setText(self.TitleText, _T(self._cfg.name))
	bee.setText(self.DescText, ItemModel:getItemDesText(self._cfg.id))
	self:refreshOwnCount()

	local recycle = self._cfg.decProps
	self._recycleCount = recycle[2]
	bee.setIconInAtlas(self.RecycleItemButton, tpl_props[recycle[1]].icon)
	bee.removeAllClick(self.RecycleItemButton)
	bee.addClick(self.RecycleItemButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = {item_id = recycle[1], num = 0}, target = self.RecycleItemButton})
	end)

	self._selectedCount = 1
	self:refreshButtonShow()
	bee.setText(self.InputFieldCount, self._selectedCount, "InputField")

	bee.removeAllClick(self.MinButton)
	bee.addClick(self.MinButton, function()
		if self._selectedCount <= 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = 0
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MaxButton)
	bee.addClick(self.MaxButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = self._maxCount
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MinusButton)
	bee.addClick(self.MinusButton, function()
		if self._selectedCount <= 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(0, self._selectedCount - 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.AddTenButton)
	bee.addClick(self.AddTenButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 10)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MinTenButton)
	bee.addClick(self.MinTenButton, function()
		if self._selectedCount <= 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(0, self._selectedCount - 10)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.addLongClick(self.MinusButton, function()
		if self._selectedCount <= 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(0, self._selectedCount - 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.AddButton)
	bee.addClick(self.AddButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)

	end)
	bee.addLongClick(self.AddButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)

	self.InputFieldCount:GetComponent("InputField").onEndEdit:RemoveAllListeners()
	self.InputFieldCount:GetComponent("InputField").onEndEdit:AddListener(function()
		local inputCount = tonumber(bee.getText(self.InputFieldCount, "InputField"))
		if not inputCount then
			inputCount = 0
		end
		if inputCount < 0 then
			inputCount = 0
		end
		if inputCount > self._maxCount then
			inputCount = self._maxCount
		end
		bee.setText(self.InputFieldCount, inputCount, "InputField")
		self._selectedCount = inputCount
		self:refreshButtonShow(consumeCount)
	end, "InputField")
end

function P:refreshOwnCount()
	local num = ItemModel:getItemNumById(self._cfg.id)
	self._maxCount = num
	bee.setText(self.Own, _F("LAB_SHOP_COMMON_23", self._maxCount))
end

function P:refreshButtonShow()
	if self._selectedCount <= 0 then
		self:setButtonShow(self.MinButton, false)
		self:setButtonShow(self.MinusButton, false)
		self:setButtonShow(self.MinTenButton, false)
	else
		self:setButtonShow(self.MinButton, true)
		self:setButtonShow(self.MinusButton, true)
		self:setButtonShow(self.MinTenButton, true)
	end
	if self._selectedCount >= self._maxCount then
		self:setButtonShow(self.MaxButton, false)
		self:setButtonShow(self.AddButton, false)
		self:setButtonShow(self.AddTenButton, false)
	else
		self:setButtonShow(self.MaxButton, true)
		self:setButtonShow(self.AddButton, true)
		self:setButtonShow(self.AddTenButton, true)
	end

	bee.setText(self.RecycleCountText, self._recycleCount * self._selectedCount)
end

function P:setButtonShow(button, isOn)
	if not button then return end
	local Off = self:find("Off", button)
	local On = self:find("On", button)
	Off:SetActive(not isOn)
	On:SetActive(isOn)
end

function P:onClickRecycle()
	if self._selectedCount <= 0 then
		UiManager:showToast(_T("LAB_BACKPACK_DES_12"))
		return
	end
	
	Net:sendReq("pb.RecycleItemREQ", {req_item_list = {{item_uniq_id = self._params.data.item_uniq_id, item_num = self._selectedCount}}})
	self._selectedCount = 0
end

function P:evt_ItemChangeRSP()
	self:refreshButtonShow()
	self:refreshOwnCount()
	bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
end

