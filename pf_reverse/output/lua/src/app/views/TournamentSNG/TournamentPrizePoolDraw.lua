local P = class("TournamentPrizePoolDraw", UiBase)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")

    self.Title = self:find("Title", self.Center)
    self.Title1 = self:find("Title1", self.Title)
    self.Title2 = self:find("Title2", self.Title)

    local Number = self:find("Number", self.Center)

    self.Numbers = {}
    for i = 0, 9 do
        self.Numbers[i + 1] = self:find("tournament_ppd_number_" .. i, Number)
    end

    self.Images = {}
    for i = 0, 9 do
        self.Images[i + 1] = "Tournament[tournament_ppd_number_" .. i .. "]"
    end

    self.BgRoller = self:find("BgRoller", self.Center)
    self.Item = self:find("Item", self.Center)
    self.Items = {}
    self.ItemNums = {}  -- 对应的转动数字 {{0,1}}
    self.itemWidth = 110
    self.itemHeight = 142
    self.rollerHeight = self.BgRoller.transform.sizeDelta.y
    self.scrollHeight = self.itemHeight / 2 + self.rollerHeight / 2 -- item 滚动一圈的高度
    for i = 1, 10 do
        self.Items[i] = CU.GameObject.Instantiate(self.Item, self.BgRoller.transform, false)
        self.Items[i].transform.localPosition = bee.v3((i * 110) - 55 - 550, 0)
        self.ItemNums[i] = {0, 1}
    end
    self.Item:SetActive(false)
    Number:SetActive(false)
end

function P:onShow()
    Game:playSound("sound_SNG_spin")
    self:once(4.5, function()
        self:hideUI()
        bee.emit("refreshPrizePool", true)
    end)

    local lan = LAN:getLanguage()
    if lan == "jp" then
        self.Title1:SetActive(true)
        self.Title2:SetActive(false)
    else
        self.Title1:SetActive(false)
        self.Title2:SetActive(true)
        self:find("tournament_ppd_title_01_zh_add", self.Title2):SetActive(lan == "zh")
        self:find("tournament_ppd_title_02_zh", self.Title2):SetActive(lan == "zh")
        self:find("tournament_ppd_title_01_tw_add", self.Title2):SetActive(lan == "tw")
        self:find("tournament_ppd_title_02_tw", self.Title2):SetActive(lan == "tw")
        self:find("tournament_ppd_title_01_en_add", self.Title2):SetActive(lan == "en")
        self:find("tournament_ppd_title_02_en", self.Title2):SetActive(lan == "en")
    end

    self._data = self._params and self._params.data or {rate = 1, total_reward = 10000}
    self._prizeNums = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0}  -- 最终奖池数字
    local num = self._data.total_reward
    for i = #self.Numbers, 1, -1 do
        local v = self.Numbers[i]
        local n = num % 10
        num = math.floor(num / 10)
        bee.setIcon(v, self.Images[n + 1])
        self._prizeNums[i] = n
    end
    for k, v in ipairs(self._prizeNums) do
        if v == 0 then
            self.Numbers[k]:SetActive(false)
        else
            break
        end
    end

    -- for k, v in ipairs(self._prizeNums) do
    --     self:once(0.05 * (k - 1), function()
    --         self:startRoleToNum(self.Items[k], self.ItemNums[k], v)
    --     end)
    -- end
end

function P:startRoleToNum(item, nums, toNum)
    self:refreshItem(item, nums)
    local y = self.scrollHeight * (20 + toNum)
    local pos = item.transform.localPosition
    local num1, num2 = self:find("num1", item), self:find("num2", item)
    bee.tween(item)
    : to(1.5, {position = bee.v3(pos.x, -y, 0)})
    : ease(DT.Ease.InOutSine)
    : onUpdate(function()
        local pos2 = item.transform.localPosition
        if math.floor(-pos.y / self.scrollHeight) ~= math.floor(-pos2.y / self.scrollHeight) then
            pos = pos2
            local index = math.floor(-pos2.y / self.scrollHeight)
            local p1, p2 = num1.transform.localPosition, num2.transform.localPosition
            p1.y = 0 + self.scrollHeight * index
            p2.y = self.scrollHeight + self.scrollHeight * index
            num1.transform.localPosition, num2.transform.localPosition = p1, p2
            nums[1] = index % 10
            nums[2] = (nums[1] + 1) % 10
            self:refreshItem(item, nums)
        end
    end)
    : onComplete(function()
        bee.setIcon(num1, self.Images[toNum + 1])
        bee.setIcon(num2, self.Images[toNum + 1])
    end)
    : link()
end

function P:refreshItem(item, nums)
    for k, v in ipairs(nums) do
        bee.setIcon(self:find("num" .. k, item), self.Images[v + 1])
    end
end

return P