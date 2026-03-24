local P = class("GachaMainDetail", UiDialog)

local DetailKind = {
	Explain = 1,
	Title = 2,
	Role = 3,
	Prop = 4,
}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.TitleText = self:find("TitleText", Center)
	self.ItemExplain = self:find("ItemExplain", Center)
	self.ItemTitle = self:find("ItemTitle", Center)
	self.ItemRoleRow = self:find("ItemRoleRow", Center)
	self.ItemPropRow = self:find("ItemPropRow", Center)
	self.DetailList = self:find("DetailList", Center)
	self.Empty = self:find("Empty", Center)
	self.ItemExplain:SetActive(false)
	self.ItemTitle:SetActive(false)
	self.ItemRoleRow:SetActive(false)
	self.ItemPropRow:SetActive(false)

	self.CloseButton = self:find("CloseButton", Center)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
    
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)

	self.TextInsertImage = AnimRoot:GetComponent("TextInsertImage")
end

function P:onStart()
	self:initList()
	self:setDetailList()

	local poolCfg = tpl_card_pool[self._params.id]
	if poolCfg then
		bee.setText(self.TitleText, _F("LAB_GACHA_008", _T(poolCfg.name)))
	else
		bee.setText(self.TitleText, _T("LAB_TIP"))
	end
end

function P:evt_gachaUpdate()
	self:setDetailList()
end

function P:initList()
	self.detailList = UiListEx:create(self.DetailList)
	self.detailList:setCreateFunc(function(data)
		local item
		if data.__kind == DetailKind.Explain then
			item = self.ItemExplain
		elseif data.__kind == DetailKind.Title then
			item = CU.GameObject.Instantiate(self.ItemTitle)
		elseif data.__kind == DetailKind.Role then
			item = CU.GameObject.Instantiate(self.ItemRoleRow)
		else
			item = CU.GameObject.Instantiate(self.ItemPropRow)
		end
		item:SetActive(true)
		return item
	end)
	self.detailList:setRefreshFunc(function(data, item)
		if data.__kind == DetailKind.Explain then
			self:setItemExplain(item, data)
		elseif data.__kind == DetailKind.Title then
			self:setItemTitle(item, data)
		elseif data.__kind == DetailKind.Role then
			self:setItemRoleRow(item, data)
		else
			self:setItemPropRow(item, data)
		end
	end)
	self.detailList:setTopBottom(0, 30)
	self.detailList:setWidth({
		[DetailKind.Explain] = 440,
		[DetailKind.Title] = 95,
		[DetailKind.Role] = 225,
		[DetailKind.Prop] = 225,
	})
end

local ROW_COUNT = 6
function P:setDetailList()
	local poolList = GachaModel:getCardPoolListById(self._params.id)

	local roleList = {}
	local decorationList = {}
	local giftList = {}

	if poolList then
		for i,v in ipairs(poolList) do
			if v.content_type == CARD_CONTENT_TYPE.CHARACTER then
				table.insert(roleList, v)
			elseif v.content_type == CARD_CONTENT_TYPE.DECORATION then
				table.insert(decorationList, v)
			elseif v.content_type == CARD_CONTENT_TYPE.GIFT then
				table.insert(giftList, v)
			end
		end
	end

	local showData = {}

	if poolList then
		table.insert(showData, {__kind = DetailKind.Explain})

		table.insert(showData, {__kind = DetailKind.Title, id = CARD_CONTENT_TYPE.CHARACTER})
		for i = 1, #roleList, ROW_COUNT do
			local rowItems = {}
			for j = i, i + ROW_COUNT do
				if roleList[j] then
					table.insert(rowItems, roleList[j])
				else
					break
				end
			end
			table.insert(showData, {__kind = DetailKind.Role, rowItems = rowItems})
		end

		table.insert(showData, {__kind = DetailKind.Title, id = CARD_CONTENT_TYPE.DECORATION})
		for i = 1, #decorationList, ROW_COUNT do
			local rowItems = {}
			for j = i, i + ROW_COUNT do
				if decorationList[j] then
					table.insert(rowItems, decorationList[j])
				else
					break
				end
			end
			table.insert(showData, {__kind = DetailKind.Prop, rowItems = rowItems})
		end

		table.insert(showData, {__kind = DetailKind.Title, id = CARD_CONTENT_TYPE.GIFT})
		for i = 1, #giftList, ROW_COUNT do
			local rowItems = {}
			for j = i, i + ROW_COUNT do
				if giftList[j] then
					table.insert(rowItems, giftList[j])
				else
					break
				end
			end
			table.insert(showData, {__kind = DetailKind.Prop, rowItems = rowItems})
		end
	end

	self.detailList:setDatas(showData)
	self.Empty:SetActive(#showData == 0)
end

function P:setItemExplain(item, data)
	local TipsTextCont = self:find("TipsTextCont", item)

	for i = 1, 3 do
		local TipsText = self:find("TipsText" .. i, TipsTextCont)
		local text, propCfg, key
		if i == 1 then
			propCfg = tpl_props[tpl_constdata.CharacterDropRewards]
			key = "LAB_GACHA_017"
		elseif i == 2 then
			propCfg = tpl_props[10800001]
			key = "LAB_GACHA_018"
		elseif i == 3 then
			propCfg = tpl_props[10700001]
			key = "LAB_GACHA_019"
		end
		text = _F(key, string.format("<icon name=%s event=%d scale=2 />", propCfg.icon, propCfg.id) .. "<color=#BC9240>(" .. _T(propCfg.name) .. ")</color>")

		local cmp = TipsText:GetComponent("RichText")
		bee.setText(TipsText, text, "RichText")

		cmp:RemoveAllListeners()
		cmp:AddListener(function(name, args)
			UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(propCfg.id, true)})
		end)
	end

	local Probability = self:find("Probability", item)
	bee.setText(self:find("Rate1/RateText", Probability), GachaModel:getCardPoolCharacterRate(self._params.id) .. "%")
	bee.setText(self:find("Rate2/RateText", Probability), GachaModel:getCardPoolCosmeticRate(self._params.id) .. "%")
	bee.setText(self:find("Rate3/RateText", Probability), GachaModel:getCardPoolItemRate(self._params.id) .. "%")

	bee.setText(self:find("TipsText4", TipsTextCont), _T("LAB_GACHA_020"))
end

function P:setItemTitle(item, data)
	local LabelImage = self:find("LabelImage", item)
	local TitleText = self:find("TitleText", item)
	local RateText = self:find("RateText", item)

	if data.id == CARD_CONTENT_TYPE.CHARACTER then
		bee.setIcon(LabelImage, "gacha_label_03", "Gacha")
		bee.setText(TitleText, _T("LAB_GACHA_014"))
		bee.setText(RateText, GachaModel:getCardPoolCharacterRate(self._params.id) .. "%")
	elseif data.id == CARD_CONTENT_TYPE.DECORATION then
		bee.setIcon(LabelImage, "gacha_label_02", "Gacha")
		bee.setText(TitleText, _T("LAB_GACHA_015"))
		bee.setText(RateText, GachaModel:getCardPoolCosmeticRate(self._params.id) .. "%")
	elseif data.id == CARD_CONTENT_TYPE.GIFT then
		bee.setIcon(LabelImage, "gacha_label_01", "Gacha")
		bee.setText(TitleText, _T("LAB_GACHA_016"))
		bee.setText(RateText, GachaModel:getCardPoolItemRate(self._params.id) .. "%")
	end
end

function P:setItemRoleRow(item, data)
	for i = 1, ROW_COUNT do
		local ItemRole = self:find("ItemRole" .. i, item)
		if data.rowItems[i] then
			ItemRole:SetActive(true)
			self:setItemRole(ItemRole, data.rowItems[i])
		else
			ItemRole:SetActive(false)
		end
	end
end

function P:setItemRole(item, data)
	local RoleIcon = self:find("RoleIcon", item)
	local UpTag = self:find("UpTag", item)
	local UpTips = self:find("UpTips", item)
	local RateTips = self:find("RateTips", item)

	local roleCfg = tpl_character[data.content_id]
	bee.setIconInAtlas(RoleIcon, tpl_props[roleCfg.avatar].icon)

	UpTag:SetActive(data.weight_up)
	UpTips:SetActive(data.weight_up)

	if data.weight_up then
		bee.setText(UpTips, data.probability * 100 .. "%")
	end

	bee.setText(RateTips, data.totalRate * 100 .. "%")

	bee.removeAllClick(RoleIcon)
	bee.addClick(RoleIcon, function()
		Game:playSound("ui_button_confirm")
		local skins = get_tpl_subKey(tpl_character_skin_list, "role", data.content_id)
		UiManager:showUI("CharacterMain", {skin_id = skins[1].id})
	end)
end

function P:setItemPropRow(item, data)
	for i = 1, ROW_COUNT do
		local ItemProp = self:find("ItemProp" .. i, item)
		if data.rowItems[i] then
			ItemProp:SetActive(true)
			self:setItemProp(ItemProp, data.rowItems[i])
		else
			ItemProp:SetActive(false)
		end
	end
end

function P:setItemProp(item, data)
	local PropItemObj = self:find("PropItem", item)
	local UpTag = self:find("UpTag", item)
	local UpTips = self:find("UpTips", item)
	local RateTips = self:find("RateTips", item)

	PropItem:create(PropItemObj, {item_id = data.content_id}):bindDetail()

	UpTag:SetActive(data.weight_up)
	UpTips:SetActive(data.weight_up)

	if data.weight_up then
		bee.setText(UpTips, data.probability * 100 .. "%")
	end

	bee.setText(RateTips, data.totalRate * 100 .. "%")
end

