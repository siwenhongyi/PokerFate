local P = class("ShopDecorateTheme", UiBase)

function P:onAwake()
	self.ThemeItem = self:find("ThemeItem")
	self.ThemeItemList = self:find("ThemeItemList")
	self.ThemeItem:SetActive(false)
end

function P:onStart()
	self.themeList = UiListEx:create(self.ThemeItemList)
	self.themeList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ThemeItem)
	end)
	self.themeList:setRefreshFunc(function (data, item, isInit, index)
		self:setThemeItem(item, data, isInit, index)
	end)
	self.themeList:setWidth(615)

	self._timeTags = {}

	self:setThemeList()

	ShopModel:refreshNewItemByShopType(SHOP_TYPE.shop_theme, true)
	ShopModel:refreshTimeLimitItemByShopType(SHOP_TYPE.shop_theme, true)
	ShopModel:refreshShopNewTag(SHOP_TYPE.shop_theme)
end

function P:refreshUI()
	self:setThemeList()
end

function P:setThemeList()
	self.themeList:setDatas(ShopModel:getThemeList())

	if self._selelctItem then
		for k, v in pairs(self.themeList:getDatas()) do
			if v.data.id == self._selelctItem then
				self.themeList:moveToYItem(k)
				UiManager:showUI("ShopPurchaseTheme", {data = v.data})
				return
			end
		end
		self._selelctItem = nil
	end
end

function P:setThemeItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local LobbyImg = self:find("Mask/LobbyImg", Ani_root)
	local NameText = self:find("NameText", Ani_root)
	local DescText = self:find("DescText", Ani_root)
	local NewTag = self:find("NewTag", Ani_root)
	local Preview = self:find("Preview", Ani_root)
	local CountDown = self:find("CountDown", Ani_root)
	local CountDown1 = self:find("CountDown1", Ani_root)
	local PreviewButton = self:find("PreviewButton", Ani_root)
	local OwnTag = self:find("OwnTag", Ani_root)
	local Discount = self:find("Discount", Ani_root)
	local DiscountText = self:find("DiscountText", Discount)
	local OriPri = self:find("OriPri", Ani_root)
	local CurPri = self:find("CurPri", Ani_root)
	local IncludeItemList = self:find("IncludeItemList/Viewport/Content", Ani_root)
	local IncludeItem = self:find("IncludeItemList/IncludeItem", Ani_root)
	IncludeItem:SetActive(false)

	if isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_ShopDecorateTheme", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

	bee.setIconInAtlas(LobbyImg, data.show_image)
	bee.setText(NameText, _T(data.name))
	bee.setText(DescText, _T(data.theme_des))

	NewTag:SetActive(ShopModel:isShowNewTag(data))

	if self._timeTags[item] then
		scheduler:removeTag(self._timeTags[item])
	end

	if data.time_end then
		local leftTime = data.time_end - bee.getServerTime()
		if leftTime > 0 then
			self:_setTimeShow(Ani_root, leftTime)
			self._timeTags[item] = bee.schedule(1, function()
				leftTime = leftTime - 1
				self:_setTimeShow(Ani_root, leftTime)
			end, item)
		else
			self:_setTimeShow(Ani_root, leftTime)
		end
	else
		CountDown:SetActive(false)
		CountDown1:SetActive(false)
	end

	if data.isOwn then
		OwnTag:SetActive(true)
		Discount:SetActive(false)
		OriPri:SetActive(false)
		CurPri:SetActive(false)
	else
		OwnTag:SetActive(false)
		Discount:SetActive(true)
		OriPri:SetActive(true)
		CurPri:SetActive(true)

		bee.setIconInAtlas(self:find("Icon", OriPri), tpl_props[data.consumeId].icon)
		bee.setIconInAtlas(self:find("Icon", CurPri), tpl_props[data.consumeId].icon)
		bee.setText(self:find("PriText", OriPri), data.oriPri)
		bee.setText(self:find("PriText", CurPri), data.pri)
		bee.setText(DiscountText, ((1000 - data.discount) / 10) .. "%")
	end

	local rewardCount = #data.items
	local childCount = IncludeItemList.transform.childCount
	for i = 1, rewardCount do
		if i > childCount then
			local p = CU.GameObject.Instantiate(IncludeItem)
			p.transform:SetParent(IncludeItemList.transform)
			p.transform.localPosition = bee.v3(0, 0, 0)
			p.transform.localScale = bee.v3(1, 1, 1)
			p:SetActive(true)
			
			self:setIncludeItem(p, data.items[i])
		else
			self:setIncludeItem(IncludeItemList.transform:GetChild(i - 1), data.items[i])
		end
	end
	if childCount > rewardCount then
		for i = rewardCount + 1, childCount do
			IncludeItemList.transform:GetChild(i - 1):SetActive(false)
		end
	end

	bee.removeAllClick(item)
	bee.addClick2(item, function()
		if data.new_tag == 1 then
			NewTag:SetActive(false)
			ShopModel:setNewItem(data)
		end

		if data.isOwn then
			UiManager:showToast(_T("LAB_SHOP_COMMON_16"))
			return
		end
		Game:playSound("ui_button_confirm")
		UiManager:showUI("ShopPurchaseTheme", {data = data})
	end)

	bee.removeAllClick(PreviewButton)
	bee.addClick(PreviewButton, function()
		bee.logEvent("shop-goods-preview", data.shop_type, data.id)
		Game:playSound("ui_button_confirm")
		if data.new_tag == 1 then
			NewTag:SetActive(false)
			ShopModel:setNewItem(data)
		end

		UiManager:showUI("ShopThemePreview", {data = data})
	end)
end

function P:setIncludeItem(item, data)
	local PropItemObj = self:find("PropItem", item)
	local NameText = self:find("NameText", item)
	local CheckMask = self:find("CheckMask", item)
	local OwnNameText = self:find("CheckMask/OwnNameText", item)

	PropItem:create(PropItemObj, data.cfg):bindTips()
	CheckMask:SetActive(data.isOwn)

	if data.isOwn then
		NameText:SetActive(false)
		bee.setText(OwnNameText, _F("TAB_SHOP_THEME_NAME_" .. data.cfg.type, _T(data.cfg.name)))
	else
		NameText:SetActive(true)
		bee.setText(NameText, _F("TAB_SHOP_THEME_NAME_" .. data.cfg.type, _T(data.cfg.name)))
	end
end

function P:selectItem(jumpTo)
	if self.themeList then
		for k,v in pairs(self.themeList:getDatas()) do
			if v.data.id == jumpTo then
				self.themeList:moveToYItem(k)
				UiManager:showUI("ShopPurchaseTheme", {data = data})
				return
			end
		end
	else
		self._selelctItem = jumpTo
	end
end

function P:_setTimeShow(item, leftTime)
	local CountDown = self:find("CountDown", item)
	local CountDown1 = self:find("CountDown1", item)
	if leftTime > 259200 then
		CountDown:SetActive(true)
		CountDown1:SetActive(false)
		bee.setText(self:find("TimeText", CountDown), ShopModel:getShopTimeText(leftTime))
	elseif leftTime > 0 then
		-- 小于3天
		CountDown:SetActive(false)
		CountDown1:SetActive(true)
		bee.setText(self:find("TimeText", CountDown1), ShopModel:getShopTimeText(leftTime))
	else
		CountDown:SetActive(false)
		CountDown1:SetActive(true)
		bee.setText(self:find("TimeText", CountDown1), _T("LAB_BACKPACK_DES_21"))
	end
end

return P