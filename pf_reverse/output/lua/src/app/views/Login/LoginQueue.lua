local P = class("LoginQueue", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.TextCount = self:find("TextCount", self.Panel)
    self.TextTime = self:find("TextTime", self.Panel)

    bee.addClick(self:find("ExitButton", self.Panel), function()
        Net:sendReq("pb.CancelLoginQueueREQ", {})
        self:hideUI()
        bee.logEvent("login-queue-cancel")
    end)
end

function P:onShow()
    self._data = self._params or {pos = 10, est_wait_time = 60}

    self:refreshUI()

    -- self:schedule(1, function()
    --     if self._data.est_wait_time > 0 then
    --         self._data.est_wait_time = self._data.est_wait_time - 1
    --         self:refreshUI()
    --     end
    -- end)
    CS.SdkHelper.setScreenSleep(false)
    bee.logEvent("login-queue")
end

function P:refreshUI()
    bee.setText(self.TextCount, tostring(self._data.pos))
    bee.setText(self.TextTime, TimeHelp:getTimeStr(self._data.est_wait_time))
end

function P:evt_UserLoginRSP(msg)
    if 0 == msg.code then
        bee.logEvent("login-queue-success")
    end
end

function P:evt_CancelLoginQueueRSP(msg)
end

function P:evt_LoginQueueStatusChangeBRC(msg)
    self._data = msg
    self:refreshUI()
end

function P:evt_onApplicationPause(paused)
    if not paused then
        if Net:isConnected() then
		else
			UiManager:showTip({
                text = _T("LAB_LOGIN_QUEUE_INFO8"),
                button = 1,
                onSure = function()
                    LoginModel:reConnectWithCheck()
                    self:hideUI()
                end,
                onCancel = function()
                    self:hideUI()
                end
            })
		end
    end
end

return P