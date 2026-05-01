local P = class("AchievementBase", UiFullView)

function P:onAwake()
    self.RightTop = self:find("AnimRoot/RightTop")
    self.LeftTop = self:find("AnimRoot/LeftTop")
    self.LeftBottom = self:find("AnimRoot/LeftBottom")
    self.Center = self:find("AnimRoot/Center")
    local Currency = self:find("Currency", self.RightTop)

    bee.addClick(self:find("BackButton", self.LeftTop), function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)


    self.TotalValue = self:find("Total/Value", Currency)
    self.HAValue = self:find("Subdivision/01/Value", Currency)
    self.MAValue = self:find("Subdivision/02/Value", Currency)
    self.LAValue = self:find("Subdivision/03/Value", Currency)
end

--获取指定主题进度
function P:getProgress(themeId)
    local list = AchievementModel.achDic[themeId]
    local clearCount = 0
    local total = 0
    for _,v in pairs(list) do
        total = total + 1
        if v.data.status >= 2 then
            clearCount = clearCount + 1
        end
    end
    return math.floor(clearCount / total * 100)
end

--刷新成就数量
function P:evt_refreshAchievementValue(data)
    bee.setText(self.HAValue, data.dic[1])
    bee.setText(self.MAValue, data.dic[2])
    bee.setText(self.LAValue, data.dic[3])
    bee.setText(self.TotalValue, string.format("%s/%s", data.clearCount, data.total))
end




return P