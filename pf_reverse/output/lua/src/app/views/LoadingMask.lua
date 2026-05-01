local P = class("LoadingMask", UiBase)

function P:ctor()
    P.super.ctor(self)
    self.inPop = true
end

function P:onAwake()
    self._tags = {}
    self._stayTime = 20
    self.Text = self:find("Text")
end

function P:onStart()
    self.ImageBg = self:find("ImageBg")
    self.Text = self:find("Text")
    self.ImageBg:SetActive(false)
    self.Text:SetActive(false)

    self:once(0.5, function()
        self.ImageBg:SetActive(true)
        self.Text:SetActive(true)
    end)

    self:schedule(1, function()
        self._stayTime = self._stayTime - 1
        if self._stayTime <= 0 then
            self:hideUI(nil, true)
        end
    end)
end

function P:addTag(tag, tip)
    self._tags[tag] = tag
    self._stayTime = 10
    if tip then
        bee.setText(self.Text, tip)
    else
        bee.setText(self.Text, _T("LAB_LOGIN_LOADING"))
    end
end

function P:removeTag(tag)
    self._tags[tag] = nil
    if not next(self._tags) then
        self:hideUI(nil, true)
    end
end

return P