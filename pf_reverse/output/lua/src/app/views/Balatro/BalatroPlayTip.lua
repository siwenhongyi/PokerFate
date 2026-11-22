local P = class("BalatroPlayTip", Object)
BalatroPlayTip = P

function P:onAwake()
    self.Ani = self.transform:GetComponent("Animator")
    self.Icon = self:find("Image")
    self.Text = self:find("Text")
end

function P:showTip()
    self.Ani:Play("BalatroPlayTip", -1, 0)
    self:once(1, function ()
        bee.emit("evt_BalPlayTipOver", {cls = self})
    end)
end

function P:setInfo(rewId, str)
    if rewId then
        self.Icon:SetActive(true)
        if rewId == Bal.ParameterType.Chip then
            bee.setIcon(self.Icon, "Balatro[fighting_bg_fraction_b]")
        elseif rewId == Bal.ParameterType.Power or rewId == Bal.ParameterType.MulPower then
            bee.setIcon(self.Icon, "Balatro[fighting_bg_fraction_a]")
        else
            bee.setIcon(self.Icon, "Balatro[fighting_bg_fraction]")
        end

        if rewId == Bal.ParameterType.Chip or rewId == Bal.ParameterType.Power or rewId == Bal.ParameterType.HandCard or
            rewId == Bal.ParameterType.Gold or rewId == Bal.ParameterType.PlayCount or rewId == Bal.ParameterType.FoldCount then
            str = "+" .. str
        elseif rewId == Bal.ParameterType.MulPower then
            str = "x" .. str
        end
    else
        self.Icon:SetActive(false)
    end
    bee.setText(self.Text, str or "")
end


return P