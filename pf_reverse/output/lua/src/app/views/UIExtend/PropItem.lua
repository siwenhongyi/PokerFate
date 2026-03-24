local P = class("PropItem", Object)
PropItem = P
local ItemBgList = {
	[0] = "Common[common_item_grid_m_01]",
	[1] = "Common[common_item_grid_m_02]",
	[2] = "Common[common_item_grid_m_03]",
	[3] = "Common[common_item_grid_m_04]",
	[4] = "Common[common_item_grid_m_05]",
	[5] = "Common[common_item_grid_m_06]",
}

-- 绑定物品节点
function P:bindItemNode(node, data)
	local cls = ObjectPool:getCls(self.node)
	if cls then
		if data then
			cls:setData(data)
		end
	else
		cls = P:create(node, data)
	end
	return cls
end

function P:ctor(node, data)
	if node then
		self.node = node.gameObject or node
		self:initUI()
		local cls = ObjectPool:getCls(self.node)
		if cls then
			ObjectPool:unbindObj(self.node)
		end
		ObjectPool:bindObj(self.node, self)
	end
	if data then
		self:setData(data)
	end
end

function P:onAwake()
	self:initUI()
	self:on("init", function(data)
		self:setData(data, setting)
	end)
end

function P:initUI()
	self.ItemBg = self:find("ItemBg")
	self.Icon = self:find("Icon")
	self.CountText = self:find("CountText")
	self.TimeTag = self:find("TimeTag")
	self.TimeText = self:find("TimeText", self.TimeTag)
	self.LinkTag = self:find("LinkTag")
end

local ICON_SCALE = 128 / 160
function P:setData(data)
	self.data = data
	self.id = data.item_id or data.id
	self.icon = data.icon

	self:refreshUI()
end

function P:refreshUI()
	local cfg = tpl_props[self.id]

	if not cfg or not self.data then
		printError("[ItemModel] add item with no cfg id " .. self.id)
		return
	end

	-- 图标
	if self.icon then
		bee.setIconInAtlas(self.Icon, self.icon, self.ItemBg ~= nil)
	else
		bee.setIconInAtlas(self.Icon, cfg.icon, self.ItemBg ~= nil)
	end

	-- 背景
	if cfg.type == GPropKind.LobbyScene or cfg.type == GPropKind.Table or cfg.type == GPropKind.AllInEff then
		if self.ItemBg then
			self.ItemBg:SetActive(false)
		end
		self.Icon.transform.localScale = bee.v3(1, 1, 1)
	else
		if self.ItemBg then
			self.ItemBg:SetActive(true)
			bee.setIcon(self.ItemBg, ItemBgList[cfg.quality])
			local s1, s2 = self.ItemBg.transform.sizeDelta, self.Icon.transform.sizeDelta
			local s = ICON_SCALE * s1.x / s2.x
			self.Icon.transform.localScale = bee.v3(s, s, 1)
		end
	end

	-- 数量
	if self.CountText then
		if self.data.num and self.data.num > 0 and ItemModel:getGPropType(cfg.type) ~= GPropType.Display then
			self.CountText:SetActive(true)
			bee.setTextGold(self.CountText, _N(self.data.num))
		else
			self.CountText:SetActive(false)
		end
	end

	-- 限时
	if self._timeCountDown then
		scheduler:removeTag(self._timeCountDown)
		self._timeCountDown = nil
	end
	if cfg.duration or cfg.expirationTime then
		self:setTimeText(self.data.deadline)
	else
		if self.TimeTag then
			self.TimeTag:SetActive(false)
		end
	end

	-- 绑定
	if self.LinkTag then
		if cfg.isBinding and cfg.isBinding == 1 then
			self.LinkTag:SetActive(true)
		else
			self.LinkTag:SetActive(false)
		end
	end
end

function P:setTimeText(deadline)
	if not self.TimeTag then
		return
	end

	if not deadline then
		self.TimeTag:SetActive(false)
		return
	end

	self.TimeTag:SetActive(true)

	local dt = self.data.deadline - bee.getServerTime()
	if dt <= 0 then
		bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
		return
	end

	bee.setText(self.TimeText, ItemModel:getPropItemTimeStr(dt))
	self._timeCountDown = self:schedule(1, function()
		dt = dt - 1
		if dt > 0 then
			bee.setText(self.TimeText, ItemModel:getPropItemTimeStr(dt))
		else
			bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
			scheduler:removeTag(self._timeCountDown)
			self._timeCountDown = nil
		end
	end)
end

function P:setItemBg(itemBg, data)
	local cfg = tpl_props[data.item_id or data.id]
	if cfg then
		bee.setIcon(itemBg, ItemBgList[cfg.quality])
	end
end

function P:bindDetail(cb, jumpCb)
	bee.removeAllClick(self.node)
	bee.addClick(self.node, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(self.id, true), jumpCb = jumpCb})
		if cb then
			cb()
		end
	end, true)
	return self
end

function P:bindTips(parent)
	bee.removeAllClick(self.node)
	bee.addClick(self.node, function()
		if bee.isNull(self.node) then
			return
		end
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = self.data, target = self.node, parent = parent})
	end, true)
	return self
end

function P:bindPreview()
	bee.removeAllClick(self.node)
	bee.addClick(self.node, function()
		if bee.isNull(self.node) then
			return
		end
		Game:playSound("ui_button_confirm")
		local cfg = tpl_props[self.id]
		if not cfg.preview then
			return
		end
		UiManager:hideUI("CommonItemTip")
		if cfg.type == GPropKind.MusicLobby or cfg.type == GPropKind.MusicTable then
			UiManager:showUI("BackpackMusic", {data = ItemModel:getItem(self.id, true)})
		elseif cfg.type == GPropKind.LobbyScene then
			UiManager:showUI("BackpackLobbyPreview", {data = ItemModel:getItem(self.id, true), list = {ItemModel:getItem(self.id, true)}})
		else
			UiManager:showUI("BackpackPreview", {data = ItemModel:getItem(self.id, true)})
		end
	end, true)
	return self
end

function P:hideNum()
	self.CountText:SetActive(false)
end

function P:hideLinkTag()
	self.LinkTag:SetActive(false)
end

function P:hideBg()
	if self.ItemBg then
		self.ItemBg:SetActive(false)
	end
end

