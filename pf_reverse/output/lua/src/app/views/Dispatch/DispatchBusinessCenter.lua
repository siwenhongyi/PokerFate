local P = class("DispatchBusinessCenter", Object)

function P:onAwake()
	local TabTop = self:find("TabTop")
	self.Tabs = {
		self:find("TabPackage", TabTop),
		self:find("TabItemShop", TabTop),
	}

	for k, v in ipairs(self.Tabs) do
		bee.onCheck(v, function(isOn)
			if isOn and not self._watiStart then
				if k == 1 then
					bee.logEvent("dispatch-up-shop-gift")
				elseif k == 2 then
					bee.logEvent("dispatch-up-shop-item")
				end
				self:showView(k)
			end
		end)
	end

	self.ManagementList = self:find("ManagementList")
	local item2 = self:find("item1", self.ManagementList)
	item2:SetActive(false)

	self.ShopList2 = UiListEx:create(self.ManagementList)
    self.ShopList2:setCreateFunc(function()
        return CU.GameObject.Instantiate(item2)
    end)
    self.ShopList2:setRefreshFunc(function(data, item, isInit, index)
        self:setShopItem2(item, data, index)
    end)
    self.ShopList2:setWidth(520)
	self.ShopList2:setRowCount(4)

	self.ValuePackList = self:find("ValuePackList")
	local Item1 = self:find("Item1", self.ValuePackList)
	Item1:SetActive(false)

	self.ShopList1 = UiListEx:create(self.ValuePackList)
    self.ShopList1:setCreateFunc(function()
        return CU.GameObject.Instantiate(Item1)
    end)
    self.ShopList1:setRefreshFunc(function(data, item, isInit, index)
        self:setShopItem1(item, data, index)
    end)
    self.ShopList1:setWidth(450)
	self.ShopList1:setSpacing(20)

	self.Views = {
		self.ValuePackList,
		self.ManagementList,
	}
	self._datas = {}
end

function P:onStart()
	local s = self.ShopList2._content.transform.sizeDelta
	s.x = self.ManagementList.transform.rect.width
	self.ShopList2._content.transform.sizeDelta = s
	
	self:showView(1)
end

function P:showView(index)
	self._showIndex = index

	for k, v in ipairs(self.Views) do
		v:SetActive(k == index)
	end

	local key = "_initShop" .. index
	if not self[key] then
		self[key] = true
		local datas = {}
		for _, v in ipairs(tpl_shop_dispatch_list) do
			if v.tabs == index then
				table.insert(datas, v)
			end
		end
		self._datas[index] = datas
		self:refreshDatas()
	end
end

function P:refreshDatas()
	local datas = self._datas[self._showIndex]
	if datas then
		for _, v in ipairs(datas) do
			v.leftCount = 1
			if v.limit_count and v.limit_count > 0 then
				v.leftCount = v.limit_count - ShopModel:getLimitGoodsBoughtCount(v.shop_type, v.id)
			end
		end
		table.sort(datas, function(a, b)
			if a.leftCount ~= b.leftCount then
				if a.leftCount == 0 then
					return false
				elseif b.leftCount == 0 then
					return true
				end
			end
			return a.index > b.index
		end)
		self["ShopList" .. self._showIndex]:setDatas(datas)
	end
end

local _posList = {
	{{0, 0}},
	{{-83, 0}, {83, 0}},
	{{-83, 158.5}, {83, 158.5}, {0, -33.5}},
	{{-83, 158.5}, {83, 158.5}, {-83, -33.5}, {83, -33.5}},
}
function P:setShopItem1(item, data, index)
	local Ani_root = self:find("Ani_root", item)

	bee.setText(self:find("TextName", Ani_root), _T(data.name))
	
	local pidCfg = ShopModel:getPidData(data.buy_id)
	bee.setText(self:find("TextPrice", Ani_root), ShopModel:getPriText(pidCfg))

	local BgItems = self:find("BgItems", Ani_root)
	self:removeAllChildren(BgItems)
	
	local Item = self:find("Item", Ani_root)
	Item:SetActive(false)

	local poses = _posList[math.floor(#data.props / 2)]

	local ii = 1
	for i = 1, #data.props - 1, 2 do
		local node = CU.GameObject.Instantiate(Item, BgItems.transform, false)
		node:SetActive(true)
		
		bee.setText(self:find("TextNum", node), "x " .. (data.props[i + 1] or 1))
		bee.setIcon(self:find("Icon", node), tpl_props[data.props[i]].icon)

		bee.addClick(node, function()
			Game:playSound("ui_button_confirm")
			UiManager:showUI("CommonItemTip", {data = {id = data.props[i], num = data.props[i + 1]}, target = node})
		end)

		node.transform.localPosition = bee.v3(poses[ii][1], poses[ii][2])
		ii = ii + 1
	end

	local buyCount = ShopModel:getLimitGoodsBoughtCount(data.shop_type, data.id)
    ShopModel:setShopLimitStr(self:find("TextLimit", Ani_root), data.limit_type, data.limit_count, buyCount)
	self:find("shop_gacha_item_bg_mask", Ani_root):SetActive(data.limit_count and buyCount >= data.limit_count)

	bee.addClick(item, function()
		Game:playSound("ui_button_confirm")
		if data.limit_count and buyCount >= data.limit_count then
			return
		end
		ShopModel:pay(data)
	end, true)
end

function P:setShopItem2(item, data, index)
	local Ani_root = self:find("Ani_root", item)

	bee.setText(self:find("TextNum", Ani_root), "x " .. (data.props[2] or 1))
	bee.setIcon(self:find("Icon", Ani_root), data.icon)

	local TextName = self:find("BgName/TextName", Ani_root)
	bee.setText(TextName, _T(data.name))
	GF.autoScrollText(TextName)
	
	local pidCfg = ShopModel:getPidData(data.buy_id)
	bee.setText(self:find("TextPrice", Ani_root), ShopModel:getPriText(pidCfg))

	bee.addClick(item, function()
		Game:playSound("ui_button_confirm")
		ShopModel:pay(data)
	end, true)
end

function P:evt_pay_sucess()
	if 1 == self._showIndex then
		self:refreshDatas()
	else
		self:refreshDatas()
	end
end

return P