local P = class("DevelopmentFundReward", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)

    self.Item = self:find("Obtain/Item", self.Center)

    bee.addClick2(self:find("common_panel_mask_70", self.AnimRoot), function()
        self:hideUI()
    end)
end

function P:onShow()
    bee.setText(self:find("TextNum1", self.Item), string.formatnumberthousands(self._params.reward))
    bee.setText(self:find("TextNum2", self.Item), string.formatnumberthousands(self._params.reward))
    bee.setText(self:find("TextNum3", self.Item), string.formatnumberthousands(self._params.reward))
end

return P