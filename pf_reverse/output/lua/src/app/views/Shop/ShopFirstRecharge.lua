local P = class("ShopFirstRecharge", UiBase)

function P:onAwake()
	P.super.onAwake()

	self.Ani_root = self:find("Ani_root")

	self.ItemTable = self:find("ItemTable", self.Ani_root)
	self.TableImg = self:find("TableImg", self.ItemTable)
	self.TableNameText = self:find("TableNameText", self.ItemTable)
	self.ViewButton = self:find("ViewButton", self.ItemTable)

	self.itemList = {}
	for i = 1, 3 do
		table.insert(self.itemList, self:find("Item" .. i, self.Ani_root))
	end

	self.RechargeButton = self:find("RechargeButton", self.Ani_root)
	self.ClaimButton = self:find("ClaimButton", self.Ani_root)
	self.ReceivedText = self:find("ReceivedText", self.Ani_root)

	bee.addClick(self.RechargeButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickRecharge()
	end)
	bee.addClick(self.ClaimButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickClaimButton()
	end)
end

function P:onStart()
	P.super.onStart()

	self._cfg = tpl_first_recharge[1]
	local rewards = ShopModel:getRewardsListWithType(self._cfg.rewards)

	local tablePropCfg = tpl_props[rewards[1].id]
	local tableCfg = tpl_card_table[tablePropCfg.mapId]
	bee.setIcon(self.TableImg, tableCfg.image)
	bee.setText(self.TableNameText, _T(tablePropCfg.name))

	for i = 1, 3 do
		local item = self.itemList[i]
		local prop = PropItem:create(self:find("PropItem", item), rewards[i + 1])
		prop:hideBg()
		prop:bindTips()
		bee.setText(self:find("PropNameText", item), _T(tpl_props[rewards[i + 1].id].name))
	end

	bee.removeAllClick(self.ItemTable)
	bee.addClick(self.ItemTable, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-firstpurchase-preview")
		UiManager:showUI("BackpackPreview", {data = rewards[1]})
	end)

	self:refreshUI()
end

function P:refreshUI()
	if ShopModel:isClaimedFirstRecharge() then
		self.ReceivedText:SetActive(true)
		self.ClaimButton:SetActive(false)
		self.RechargeButton:SetActive(false)
	elseif ShopModel:isCanGetFirstRechargeReward() then
		self.ReceivedText:SetActive(false)
		self.ClaimButton:SetActive(true)
		self.RechargeButton:SetActive(false)
	else
		self.ReceivedText:SetActive(false)
		self.ClaimButton:SetActive(false)
		self.RechargeButton:SetActive(true)
	end
end

function P:onClickRecharge()
	bee.logEvent("shop-firstpurchase-go")
	ItemModel:jumpView(self._cfg.jump)
end

function P:onClickClaimButton()
	bee.logEvent("shop-firstpurchase-claim")
	ShopModel:requestReward(self._cfg.shop_type, self._cfg.id)
end

return P