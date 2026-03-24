local P = class("ActivityLinkEmail", UiBase)

function P:onAwake()
	local Center = self:find("AnimRoot/Center")

	self.ClaimedButton = self:find("ClaimedButton", Center)
	self.LinkButton = self:find("LinkButton", Center)
	self.ClaimButton = self:find("ClaimButton", Center)
	self.PropItem1 = self:find("Bonus/PropItem1", Center)
	self.PropItem2 = self:find("Bonus/PropItem2", Center)

	bee.addClick(self.ClaimedButton, function()
		UiManager:showToast(_T("LAB_EVENT_LINKLIMIT"))
	end)
	bee.addClick(self.LinkButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickLinkButton()
	end)
	bee.addClick(self.ClaimButton, function()
		self:onClickClaimButton()
	end)
end

function P:onStart()
	self:refreshButtonShow()

	local rewards = ShopModel:getRewardsList(tpl_constdata.Linkmail_Rewards)
	PropItem:create(self.PropItem1, rewards[1]):bindTips()
	PropItem:create(self.PropItem2, rewards[2]):bindTips()
end

function P:refreshButtonShow()
	local email = PlayerModel:getBindEmail()
	if not email or "" == email then
    	self.LinkButton:SetActive(true)
    	self.ClaimButton:SetActive(false)
    	self.ClaimedButton:SetActive(false)
    elseif ActivityModel:isCanReceiveLinkRw() then
    	self.LinkButton:SetActive(false)
    	self.ClaimButton:SetActive(true)
    	self.ClaimedButton:SetActive(false)
    else
    	self.LinkButton:SetActive(false)
    	self.ClaimButton:SetActive(false)
    	self.ClaimedButton:SetActive(true)
    end
end

function P:onClickLinkButton()
	UiManager:showUI("SettingBindEmail")
end

function P:onClickClaimButton()
	ActivityModel:receiveEmailBindReward()
end

function P:evt_refreshEmailBindRw()
	self:refreshButtonShow()
end

