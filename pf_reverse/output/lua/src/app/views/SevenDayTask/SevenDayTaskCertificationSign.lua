local P = class("SevenDayTaskCertificationSign", UiDialog)

require "engine.base64"

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.ClickText = self:find("ClickText", Center)
	self.DrawCont = self:find("DrawCont", Center)
	self.HandwritingInput = self.DrawCont.transform:GetComponent("HandwritingInput")
	self.CloseButton = self:find("CloseButton", Center)

	self.CancelButton = self:find("CancelButton", Center)
	bee.addClick(self.CancelButton, function()
		bee.logEvent("7daytask-task-certified-reset")
		self:onClickReset()
	end)
	self.ConfirmButton = self:find("ConfirmButton", Center)
	bee.addClick(self.ConfirmButton, function()
		bee.logEvent("7daytask-task-certified-confirm")
		self:onClickConfirmButton()
	end)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
end

function P:onClickReset()
	self.HandwritingInput.enabled = true
	self.HandwritingInput:ClearDrawing()
	self.ClickText:SetActive(true)
end

function P:onClickConfirmButton()
	self.HandwritingInput.enabled = false
	local params = {}
    params.text = _T("LAB_SEVEN_DAY_TASKS_DEC_30")
    params.onSure = function()
        self.HandwritingInput:SaveDrawing(CS.FileUtils.GetWritePath(), "Sign_Texture_" .. PlayerModel:getUid())

        local img = CS.FileUtils.ReadAllBytesSafely(CS.FileUtils.GetWritePath() .. "Sign_Texture_" .. PlayerModel:getUid() .. ".png")
        SevenDayTaskModel:sendCertificationSign(base64encode(img), function(url)
        	if self._params.closeCb then
        		self._params.closeCb(url)
        	end
        	self:hideUI()
    	end)
    end
    params.onCancel = function()
    	self.HandwritingInput.enabled = true
	end
    UiManager:showTip(params)
end

function P:evt_beginDraw()
	self.ClickText:SetActive(false)
end

