local P = class("ShareMain", UiDialog)

local CodeImg = {
	[1] = "Share[share_img_qrcode_02]",
	[2] = "Share[share_img_qrcode_02]",
	[3] = "Share[share_img_qrcode_02]",
	[4] = "Share[share_img_qrcode_02]",
	[7] = "Share[share_img_qrcode_02]",
	[8] = "Share[share_img_qrcode_02]",
	-- 
	[5] = "Share[share_img_qrcode_01]",
	[6] = "Share[share_img_qrcode_01]",

	[9] = "Share[share_img_qrcode_03]",
	[10] = "Share[share_img_qrcode_03]",
}

function P:onAwake()
	P.super.onAwake(self)
	local AnimRoot = self:find("AnimRoot")

	self.ShowCont = self:find("ShowCont", AnimRoot)
	self.ShotCont = self:find("ShotCont", AnimRoot)
	self.ShareImg = self:find("ShareImg", AnimRoot)
	self.ShareImg:SetActive(false)
	self.ShowCont:SetActive(false)

	self.PlayerCont = self:find("PlayerCont", self.ShotCont)
	self.NameText = self:find("NameText", self.PlayerCont)
	self.UIDText = self:find("UIDText", self.PlayerCont)
	self.Avatar = self:find("AvatarMask/Avatar", self.PlayerCont)
	self.AvatarFrame = self:find("AvatarFrame", self.PlayerCont)
	self.TextCont = self:find("TextCont", self.ShotCont)
	self.TipText = self:find("TipText", self.TextCont)
	self.TopCode = self:find("TopCode", self.ShotCont)
	self.BottomCode = self:find("BottomCode", self.ShotCont)
	
	self.BottomCont = self:find("BottomCont", self.ShowCont)
	self.ShareCont = self:find("ShareCont", self.BottomCont)
	self.DownloadButton = self:find("DownloadButton", self.ShareCont)
	self.ShareLine = self:find("ShareLine", self.ShareCont)
	self.ShareButton = self:find("ShareButton", self.ShareCont)
	self.RewardCont = self:find("RewardCont", self.BottomCont)
	self.CountText = self:find("CountText", self.RewardCont)
	self.Icon = self:find("Icon", self.RewardCont)

	bee.addClick(self.DownloadButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickDownload()
	end)
	bee.addClick(self.ShareButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickShareButton()
	end)

	self.CloseButton = self:find("CloseButton", AnimRoot)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	self.ShowCont:SetActive(false)
	self.ShowCont:SetActive(false)

	self._scale = 0.7

	self.ShareLine:SetActive(not bee.isPc)
	self.ShareButton:SetActive(not bee.isPc)
end

function P:preShow()
	self:clearUiBlur()
end

function P:onDestroy()
	P.super.onDestroy(self)
	if self._tex then
		CU.GameObject.Destroy(self._tex)
		self._tex = nil
	end
end

function P:preHide()
	bee.emit(EventDef.evt_uiBlur, false, self.__cname)
	return P.super.preHide(self)
end

function P:onStart()
	bee.logEvent("share-entrance", self._params.id, ShareModel:getPageIsShared(self._params.id) and 1 or 0)

	bee.emit("evt_shareShot")
	self:shot()
	self:setShotView()
	self:setShowCont()
end

function P:setShotView()
	AnimationMgr:clearClickEffect()
	
	if not self._params or not self._params.id then
		return
	end

	local cfg = tpl_share_config[self._params.id]
	if not cfg then
		return
	end

	if cfg.player_info == 1 then
		self.PlayerCont:SetActive(true)
		bee.setText(self.NameText, PlayerModel:getName())
		bee.setText(self.UIDText, "UID:" .. PlayerModel:getUid())
		bee.setIcon(self.Avatar, PlayerModel:getAvatarIcon())
		GF.setFrameImage(self.AvatarFrame, PlayerModel:getFrame())
	else
		self.PlayerCont:SetActive(false)
	end

	if cfg.game_logo == 1 then
		self.TopCode:SetActive(true)
		self.BottomCode:SetActive(false)
		bee.setIconInAtlas(self:find("CodeImg", self.TopCode), CodeImg[G_CHNL_ID])
	elseif cfg.game_logo == 2 then
		self.TopCode:SetActive(false)
		self.BottomCode:SetActive(true)
		bee.setIconInAtlas(self:find("CodeImg", self.BottomCode), CodeImg[G_CHNL_ID])
	else
		self.TopCode:SetActive(false)
		self.BottomCode:SetActive(false)
	end

	if cfg.share_text == 1 then
		self.TextCont:SetActive(true)
		bee.setText(self.TipText, self._params.tipsText)
	else
		self.TextCont:SetActive(false)
	end

	self.ShotCont:SetActive(true)
end

function P:setShowCont()
	if not self._params or not self._params.id then
		return
	end

	local cfg = tpl_share_config[self._params.id]
	if not cfg then
		return
	end

	-- 奖励显示
	if bee.isPc or ShareModel:getPageIsShared(cfg.id) then
		self.RewardCont:SetActive(false)
	elseif cfg.reward then
		self.RewardCont:SetActive(true)
		bee.setIconInAtlas(self.Icon, tpl_props[cfg.reward[1]].icon)
		bee.setText(self.CountText, "x" .. cfg.reward[2])
	else
		self.RewardCont:SetActive(false)
	end
end

function P:shot()
	Game:playSound("ui_share_screenshot")
	
	self.CloseButton:SetActive(false)
    self:once(0.2, function()
    	self.CloseButton:SetActive(true)
	end)

    CS.Utils.CapturePartScreen(nil, CU.Screen.width, CU.Screen.height, function(tex)
    	if self._tex then
    		CU.GameObject.Destroy(self._tex)
    		self._tex = nil
    	end
    	self._tex = tex

        self.ShareImg:GetComponent("RawImage").texture = tex

		bee.emit("evt_endShareShot")
		bee.emit(EventDef.evt_uiBlur, true, self.__cname)

		self.ShareImg:SetActive(true)
		self.ShotCont:SetActive(false)
		self.ShowCont:SetActive(true)
		self.BottomCont:SetActive(false)

		bee.tween(self.ShareImg)
		:delay(0.1)
		:to(0.2, {scale = self._scale})
		:onComplete(function()
			self.BottomCont:SetActive(true)
		end)
    end)
end

function P:onClickDownload()
	bee.logEvent("share-download", self._params.id, ShareModel:getPageIsShared(self._params.id) and 1 or 0)
	CS.Utils.SaveTexture(self._tex, 3, self:_getFileName(), function()
		UiManager:showToast(_T("LAB_SHARE_3"))
	end)
end

function P:onClickShareButton()
	bee.logEvent("share-sharebutton", self._params.id, ShareModel:getPageIsShared(self._params.id) and 1 or 0)
	ShareModel:requestSharePage(self._params.id)
	CS.Utils.NativeShare(self._tex, 3, self:_getFileName(), "", function()
	end)
end

function P:evt_updateSharedPage()
	self:setShowCont()
end

function P:_getFileName()
	if not self._fileName then
		self._fileName = "ScreenCapture/screenshot-" .. os.date("%Y%m%d%H%M%S")
	end
	return self._fileName
end

