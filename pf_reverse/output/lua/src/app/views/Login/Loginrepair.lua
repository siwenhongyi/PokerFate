local P = class("Loginrepair", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    self.TextTip = self:find("TextTip", Panel)
    self.TextUID = self:find("TextUID", Panel)
    self.TextIP = self:find("TextIP", Panel)
    self.TextDeviceID = self:find("TextDeviceID", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        bee.logEvent("login-repair-close")
        self:hideUI()
    end)
    bee.addClick(self:find("ButtonClear", Panel), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("login-repair-clearuserdata")
        UiManager:showTip({
            text = _T("LAB_LOGIN_REPAIR_08"),
            button = 2,
            onSure = function()
                local id = LocalStore:getStringForKey("device_id")
                LocalStore:DeleteAll()
                if id and "" ~= id then
                    LocalStore:setStringForKey("device_id", id)
                end
                ModelManager:clearAllData()
                UiManager:showToast(_T("LAB_LOGIN_REPAIR_11"))
                bee.logEvent("login-repair-clearuserdata-confirm")
                bee.emit("evt_try_resume_bgm")

                -- self:once(0.1, function()
                --     LocalStore:setStringForKey("load_slient_result", "suc")
                --     CS.AppLoader.ExecuteSlient(false)
                --     bee.enterScene("StartScene")
                -- end)
            end,
            onCancel = function(isClose)
                if isClose then
                    bee.logEvent("login-repair-clearuserdata-close")
                else
                    bee.logEvent("login-repair-clearuserdata-cancel")
                end
            end
        })
    end)
    bee.addClick(self:find("ButtonDelete", Panel), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("login-repair-clearupdatefiles")
        UiManager:showTip({
            text = _T("LAB_LOGIN_REPAIR_09"),
            button = 2,
            onSure = function()
                bee.logEvent("login-repair-clearupdatefiles--confirm")
                LocalStore:deleteValueForKey("app_full_version")
                LocalStore:deleteValueForKey("load_slient_result")
                CS.FileUtils.DeleteDirectory(CS.AppLoader.GetAddressWritePath());
                CS.FileUtils.DeleteDirectory(CS.AppLoader.GetAddressWriteTempPath());

                self:once(0.1, function()
                    UiManager:showTip({
                        text = _T("LAB_LOGIN_REPAIR_10"),
                        button = 1,
                        noClose = true,
                        onSure = function()
                            Game:quit()
                        end,
                    })
                end)
            end,
            onCancel = function(isClose)
                if isClose then
                    bee.logEvent("login-repair-clearupdatefiles-close")
                else
                    bee.logEvent("login-repair-clearupdatefiles-cancel")
                end
            end
        })
    end)
end

return P