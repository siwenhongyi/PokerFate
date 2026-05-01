local P = class("SevenDayTaskCertification", UiFullView)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", AnimRoot)
	self.SignatureArea = self:find("Signature/SignatureArea", Center)
	self.SignatureImg = self:find("Signature/SignatureImg", Center)
	self.EditButton = self:find("EditButton", Center)
	self.NameText = self:find("NameTab/NameText", Center)
	self.TimeText = self:find("TimeTab/TimeText", Center)
	self.SignTimeText = self:find("sdt_Certificate_paper_bg/SignTimeText", Center)
	self.SignTimeText:SetActive(false)
	self.SignatureArea:SetActive(false)

	local LeftTop = self:find("LeftTop", AnimRoot)
	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	self.CertificationEff = self:find("CertificationEff", AnimRoot)
	self.CertificationEff:SetActive(false)

	local RightBottom = self:find("RightBottom", AnimRoot)
	self.ShareCont = self:find("ShareCont", RightBottom)
	self.ShareButton = self:find("ShareButton", self.ShareCont)
	self.ShareCont:SetActive(false)

	bee.addClick(self.SignatureArea, function()
		UiManager:showUI("SevenDayTaskCertificationSign", {closeCb = function(url)
			if url and url ~= "" then
				Game:playSound("ui_7daytask_transition")
				self.CertificationEff:SetActive(true)
				self:once(1.7, function()
					self.CertificationEff:SetActive(false)
					self:refreshSign(url)
				end)
				self.SignatureArea:SetActive(false)
				bee.logEvent("7daytask-certified-finish", math.floor(bee.getServerTime() - PlayerModel:getRegisterTime()))
			end
		end})
	end)
	bee.addClick(self.EditButton, function()
		bee.logEvent("7daytask-profile-reset")
		UiManager:showUI("SevenDayTaskConsume", {confirmCb = function()
			UiManager:showUI("SevenDayTaskCertificationSign", {closeCb = function(url)
				self.CertificationEff:SetActive(true)
				self:once(1.7, function()
					self.CertificationEff:SetActive(false)
					self:refreshSign(url)
				end)
			end})
		end})
	end)
	bee.addClick(self.ShareButton, function()
		UiManager:showUI("ShareMain", {id = 5})
	end)
end

function P:onStart()
	self._isFromTable = self._params.isFromTable
	if self._params.isCertification and not self._params.info then
		-- 认证
		bee.setText(self.NameText, PlayerModel:getName())
		local registerTime = os.date("*t", PlayerModel:getRegisterTime())
		bee.setText(self.TimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_33", registerTime.year, registerTime.month, registerTime.day))
		local time = os.date("*t", bee.getServerTime())
		bee.setText(self.SignTimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_33", time.year, time.month, time.day))

		self.SignatureArea:SetActive(true)
		self.EditButton:SetActive(false)
		self:refreshSign()
	elseif self._params.info then
		-- 查看
		local info = self._params.info
		bee.setText(self.NameText, info.name)
		local registerTime = os.date("*t", info.register_time)
		bee.setText(self.TimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_33", registerTime.year, registerTime.month, registerTime.day))
		local time = os.date("*t", info.auth_cert_time)
		bee.setText(self.SignTimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_33", time.year, time.month, time.day))

		self.SignatureArea:SetActive(false)
		self:refreshSign(info.auth_cert_url)

		if info.uid == PlayerModel:getUid() and not self._params.isCertification and not self._isFromTable then
			self.EditButton:SetActive(true)
		else
			self.EditButton:SetActive(false)
		end
	end
end

function P:refreshSign(url)
	if url and url ~= "" then
		-- self.SignatureImg:GetComponent("LoadImage"):DownloadImage(url)
		bee.getDownloadImage(self.SignatureImg, url)

		self.SignTimeText:SetActive(true)
		self:setShareCont()

		if (self._params.isCertification or self._params.info.uid == PlayerModel:getUid()) and not self._isFromTable then
			self.ShareCont:SetActive(true)
		end
	end
end

function P:evt_shareShot()
    self.ShareCont:SetActive(false)
end

function P:evt_endShareShot()
	if self._params.info.uid == PlayerModel:getUid() then
		self.ShareCont:SetActive(true)
	end
end

function P:evt_updateSharedPage()
    self:setShareCont()
end

function P:setShareCont()
    local ShareReward = self:find("ShareReward", self.ShareCont)
    local Icon = self:find("Icon", ShareReward)
    local CountText = self:find("CountText", ShareReward)
    ShareModel:setShareCont(ShareReward, Icon, CountText, 5)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P