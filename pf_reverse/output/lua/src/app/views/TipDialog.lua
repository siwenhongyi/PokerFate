local P = class("TipDialog", UiBase)

function P:onAwake()
	--P.super.onAwake(self)
    self.inPop = true
	self.ImageBg = self:find("ImageBg")
	
    self.TipTitle = self:find("TipTitle", self.ImageBg)
    self.TextTip = self:find("TextTip", self.ImageBg)
    self.Button1 = self:find("Button1", self.ImageBg)
    self.Button2 = self:find("Button2", self.ImageBg)
    self.ButtonClose = self:find("ButtonClose", self.ImageBg)
end

function P:onStart()
    bee.addClick(self.ButtonClose, function ()
        self:onBtCancel()
    end)
    bee.addClick(self:find("BtSure", self.Button1), function ()
        self:onBtSure()
    end)
    bee.addClick(self:find("BtSure", self.Button2), function ()
        self:onBtSure()
    end)
    bee.addClick(self:find("BtCancel", self.Button2), function ()
        self:onBtCancel()
    end)
end

function P:onShow()
    if self._params.text then
        bee.setText(self.TextTip, self._params.text)
    end
	if self._params.title then
        bee.setText(self.TipTitle, self._params.title)
	else
        bee.setText(self.TipTitle, _T("LAB_TIP"))
    end

    if self._params.noClose then
        self.ButtonClose:SetActive(false)
    end
    if 2 == self._params.button then
        self.Button1:SetActive(false)
        self.Button2:SetActive(true)
        self:refreshButtonText(self.Button2)
    else
		self.Button1:SetActive(true)
		self.Button2:SetActive(false)
		self:refreshButtonText(self.Button1)
    end

end

function P:refreshButtonText(button)
    if self._params.sureStr then
        bee.setText(self:find("BtSure/Text", button), self._params.sureStr)
    end
    if self._params.cancelStr then
        bee.setText(self:find("BtCancel/Text", button), self._params.cancelStr)
    end
end

function P:onBtSure()
    if self._params.onSure then
        if self._params.onSure() then return end
    end
    self:hideUI()
end

function P:onBtCancel()
    if self._params.onCancel then
        if self._params.onCancel() then return end
    end
    self:hideUI()
end

