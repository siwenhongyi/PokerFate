local P = class("ActivitySocialMedia", UiBase)

local MediaUI = {
	[MediaPlatform.Facebook] = {icon = "Activity[activity_socialmedia_icon_facebook]", text = "LAB_EVENT_FOLLOWFB"},
	[MediaPlatform.Line] = {icon = "Activity[activity_socialmedia_icon_line]", text = "LAB_EVENT_FOLLOWLINE"},
	[MediaPlatform.Discord] = {icon = "Activity[activity_socialmedia_icon_discord]", text = "LAB_EVENT_FOLLOWDISCORD"},
	[MediaPlatform.X] = {icon = "Activity[activity_socialmedia_icon_twitter]", text = "LAB_EVENT_FOLLOWX"},
	[MediaPlatform.Bilili] = {icon = "Activity[activity_socialmedia_icon_bilibili]", text = "LAB_EVENT_BILIBILI"},
	[MediaPlatform.Weibo] = {icon = "Activity[activity_socialmedia_icon_weibo]", text = "LAB_EVENT_BLOG"},
	[MediaPlatform.QQ] = {icon = "Activity[activity_socialmedia_icon_qq]", text = "LAB_EVENT_QQ"},
}

function P:onAwake()
	local Center = self:find("AnimRoot/Center")

	self.itemList = {}
	for i = 1, 3 do
		table.insert(self.itemList, self:find("Item" .. i, Center))
	end
end

function P:onStart()
	local cfg = ActivityModel:getCurFollowCfg()
	self._reward = ShopModel:getRewardsList(cfg.reward)[1]
	for i = 1, 3 do
		self:setFollowItem(self.itemList[i], cfg.media_platform[i])
	end
end

function P:setFollowItem(item, mediaId)
	if not mediaId then
		item:SetActive(false)
		return
	end

	item:SetActive(true)

	local TipsIcon = self:find("TipsIcon", item)
	local TipsText = self:find("TipsText", item)
	local PropItemObj = self:find("PropItem", item)
	local ClaimedButton = self:find("ClaimedButton", item)
	local JoinButton = self:find("JoinButton", item)

	bee.setIconInAtlas(TipsIcon, MediaUI[mediaId].icon)
	bee.setText(TipsText, _T(MediaUI[mediaId].text))

	PropItem:create(PropItemObj, self._reward):bindTips()

	local isFollowed = ActivityModel:getIsFollowed(mediaId)
	ClaimedButton:SetActive(isFollowed)
	JoinButton:SetActive(not isFollowed)

	bee.removeAllClick(ClaimedButton)
	bee.addClick(ClaimedButton, function()
		UiManager:showToast(_T("LAB_EVENT_LINKLIMIT"))
	end)

	bee.removeAllClick(JoinButton)
	bee.addClick(JoinButton, function()
		Game:playSound("ui_button_confirm")
		local cfg = ActivityModel:getSocialMediaCfg(mediaId)
		if not cfg then
			return
		end
		if cfg.link then
			bee.openUrl(cfg.link)
			ActivityModel:followMedia(mediaId, function()
				self:setFollowItem(item, mediaId)
			end)
		end
		if cfg.copytext then
			CS.SdkHelper.copyText(cfg.copytext)
        	UiManager:showToast(_T("LAB_COPY_SUC"))
			ActivityModel:followMedia(mediaId, function()
				self:setFollowItem(item, mediaId)
			end)
		end
	end)
end

return P