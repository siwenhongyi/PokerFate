local P = class("LoginSetLanguage", UiBase)

function P:onAwake()
    
    local Panel = self:find("AnimRoot/Center")

    bee.addClick(self:find("ButtonClose", Panel), function()
        self:hideUI()
    end)

    self._Buttons = {
        self:find("BgMain/Button01", Panel),
        self:find("BgMain/Button02", Panel),
        self:find("BgMain/Button03", Panel),
        self:find("BgMain/Button04", Panel),
    }

    bee.addClick(self._Buttons[1], function()
        LanguageManager:setLanguage(Config.Languages[1])
        self:hideUI()
        
        bee.logEvent("login-language-type", 1)
    end)
    bee.addClick(self._Buttons[2], function()
        LanguageManager:setLanguage(Config.Languages[2])
        self:hideUI()

        bee.logEvent("login-language-type", 2)
    end)
    bee.addClick(self._Buttons[3], function()
        LanguageManager:setLanguage(Config.Languages[3])
        self:hideUI()
        bee.logEvent("login-language-type", 3)
    end)
    bee.addClick(self._Buttons[4], function()
        LanguageManager:setLanguage(Config.Languages[4])
        self:hideUI()
        bee.logEvent("login-language-type", 4)
    end)

    for k, v in ipairs(self._Buttons) do
        self:find("login_button_root_03", v):SetActive(LanguageManager:getLanguage() ~= Config.Languages[k])
        self:find("login_button_root_02", v):SetActive(LanguageManager:getLanguage() == Config.Languages[k])
    end
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

return P